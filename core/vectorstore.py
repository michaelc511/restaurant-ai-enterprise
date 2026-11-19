"""F10: Cross-encoder re-ranking - re-scores retrieved chunks for actual relevance
before they reach the LLM, instead of trusting FAISS's raw similarity ranking alone.
F12: also holds get_retriever(), the shared FAISS load-or-build pipeline every engine uses.
F18: get_retriever() now fuses that FAISS (dense/semantic) search with a BM25 (sparse/keyword)
search via reciprocal rank fusion, so an exact term FAISS's embeddings blur past (a dish name,
a price, an allergen) still surfaces, before F10's cross-encoder re-ranks the merged results.
F22: the final top_k chunks re-ranking picks are then delimiter-isolated (core/sanitize.py)
before get_retriever() returns them, so retrieved menu content is never handed to an LLM
prompt without an explicit data/instruction boundary around it.
"""
import os
import re
from typing import List

from flashrank import Ranker, RerankRequest
from langchain_classic.retrievers import EnsembleRetriever  # F18: reciprocal rank fusion
from langchain_community.document_loaders import PyPDFLoader  # F3
from langchain_community.retrievers import BM25Retriever  # F18
from langchain_community.vectorstores import FAISS  # F3
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_text_splitters import RecursiveCharacterTextSplitter  # F3

from core.domain import domain  # F12
from core.sanitize import SanitizingRetriever, wrap_with_sanitization  # F22

_ranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2")  # F10: cross-encoder re-ranking model

VECTORSTORE_DIR = f"vectorstores/{domain.NAME}"  # F12: one index folder per domain pack, shared by every engine


def rerank_documents(query: str, docs: List[Document], top_k: int = 3) -> List[Document]:
    """F10: re-score retrieved docs against the query with a cross-encoder, return the top_k most relevant."""
    if not docs:
        return docs
    passages = [{"id": i, "text": doc.page_content} for i, doc in enumerate(docs)]
    results = _ranker.rerank(RerankRequest(query=query, passages=passages))  # sorted best-first
    return [docs[r["id"]] for r in results[:top_k]]


class RerankingRetriever(BaseRetriever):
    """F10: wraps a base retriever, re-ranking its results with a cross-encoder before returning them."""

    base_retriever: BaseRetriever
    top_k: int = 3

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        docs = self.base_retriever.invoke(query)
        return rerank_documents(query, docs, top_k=self.top_k)


def wrap_with_reranking(base_retriever: BaseRetriever, top_k: int = 3) -> RerankingRetriever:
    """F10: wrap an existing retriever so its results get cross-encoder re-ranked before use.

    Usage:
        retriever = wrap_with_reranking(vectorstore.as_retriever())
    """
    return RerankingRetriever(base_retriever=base_retriever, top_k=top_k)


def split_into_chunks(documents: List[Document]) -> List[Document]:
    # F3: a domain pack can set CHUNK_SEPARATORS (e.g. the restaurant menus' dish bullets) so each item
    # stays whole in one chunk - a fixed 500-char cut split "topped with thinly | sliced avocado..." and
    # the LLM filled the gap from a neighbouring dish. Packs without it (hr) keep the original split.
    separators = getattr(domain, "CHUNK_SEPARATORS", None)
    if not separators:
        return RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50).split_documents(documents)
    # F3: exactly one item per chunk - packing two dishes into one chunk let the first dish dominate its
    # embedding, so "dragon roll" missed a chunk that started with the Sashimi Deluxe Platter
    item_start = re.compile("(?=" + "|".join(re.escape(s) for s in separators) + ")")
    long_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50, separators=[". ", " "])
    chunks = []
    for doc in documents:
        text = re.sub(r"\s+", " ", doc.page_content)  # F3: PyPDFLoader puts each word on its own line
        for piece in (p.strip() for p in item_start.split(text)):
            if not piece:
                continue
            if len(piece) <= 500:
                chunks.append(Document(page_content=piece, metadata=dict(doc.metadata)))
            else:  # F3: long non-item text (address, policies) still gets a size-based split
                chunks.extend(long_splitter.split_documents([Document(page_content=piece, metadata=dict(doc.metadata))]))
    return chunks


def _bm25_tokens(text: str) -> List[str]:  # F18: case- and punctuation-insensitive, so "dragon roll" matches "Dragon Roll,"
    return re.findall(r"\w+", text.lower())


def get_retriever(cuisine: str, embeddings, top_k: int = 3) -> SanitizingRetriever:
    """F3/F10/F12/F18/F22: load a cuisine's FAISS index from disk if it's already built, or build +
    save one, then fuse it with a BM25 keyword retriever, wrap the fused result with cross-encoder
    re-ranking, and delimiter-isolate the final chunks. Shared by every engine (plain_rag today,
    langgraph/crewai/autogen later) instead of each duplicating this load-or-build pipeline.
    """
    index_path = f"{VECTORSTORE_DIR}/{cuisine}"

    # F18: BM25 has no on-disk index of its own (langchain rebuilds it in memory from the raw
    # chunks each run), so parse + split the PDF unconditionally. This is cheap/local/no API
    # calls - the FAISS embedding step below is the expensive part the on-disk index still saves.
    loader = PyPDFLoader(str(domain.DOCS_DIR / f"{cuisine}.pdf"))  # F12: the active domain's docs
    docs = split_into_chunks(loader.load())

    if os.path.exists(index_path):  # F3: load a previously saved FAISS index...
        vectorstore = FAISS.load_local(index_path, embeddings, allow_dangerous_deserialization=True)
    else:  # ...or build one from the PDF and save it
        vectorstore = FAISS.from_documents(docs, embeddings)
        vectorstore.save_local(index_path)

    faiss_retriever = vectorstore.as_retriever(search_kwargs={"k": top_k})  # F3: dense/semantic
    if getattr(domain, "CHUNK_SEPARATORS", None):  # F18/F3: packs that opted into item chunking also get case-insensitive keywords
        bm25_retriever = BM25Retriever.from_documents(docs, preprocess_func=_bm25_tokens)  # F18: sparse/keyword
    else:  # F18: hr keeps the original whitespace tokenizer
        bm25_retriever = BM25Retriever.from_documents(docs)
    bm25_retriever.k = top_k

    hybrid_retriever = EnsembleRetriever(  # F18: reciprocal rank fusion across both result lists
        retrievers=[bm25_retriever, faiss_retriever], weights=[0.5, 0.5]
    )

    return wrap_with_sanitization(wrap_with_reranking(hybrid_retriever, top_k=top_k))  # F10/F22
