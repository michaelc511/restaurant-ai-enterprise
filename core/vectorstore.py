"""F10: Cross-encoder re-ranking - re-scores retrieved chunks for actual relevance
before they reach the LLM, instead of trusting FAISS's raw similarity ranking alone.
F12: also holds get_retriever(), the shared FAISS load-or-build pipeline every engine uses.
"""
import os
from typing import List

from flashrank import Ranker, RerankRequest
from langchain_community.document_loaders import PyPDFLoader  # F3
from langchain_community.vectorstores import FAISS  # F3
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_text_splitters import RecursiveCharacterTextSplitter  # F3

_ranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2")  # F10: cross-encoder re-ranking model

VECTORSTORE_DIR = "vectorstores"  # F12: shared by every engine's get_retriever() call


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


def get_retriever(cuisine: str, embeddings, top_k: int = 3) -> RerankingRetriever:
    """F3/F10/F12: load a cuisine's FAISS index from disk if it's already built, or build + save
    one, then wrap it with cross-encoder re-ranking. Shared by every engine (plain_rag today,
    langgraph/crewai/autogen later) instead of each duplicating this load-or-build pipeline.
    """
    index_path = f"{VECTORSTORE_DIR}/{cuisine}"

    if os.path.exists(index_path):  # F3: load a previously saved FAISS index...
        vectorstore = FAISS.load_local(index_path, embeddings, allow_dangerous_deserialization=True)
    else:  # ...or build one from the PDF and save it
        loader = PyPDFLoader(f"menus/{cuisine}.pdf")
        documents = loader.load()
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        docs = text_splitter.split_documents(documents)
        vectorstore = FAISS.from_documents(docs, embeddings)
        vectorstore.save_local(index_path)

    return wrap_with_reranking(vectorstore.as_retriever(), top_k=top_k)  # F10
