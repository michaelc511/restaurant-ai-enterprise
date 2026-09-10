"""F23: unit tests for core/vectorstore.py - re-ranking logic, with the
cross-encoder model itself mocked out so tests don't download/load a real
model or need a GPU/network to run.
"""
import sys
from types import ModuleType
from typing import List
from unittest.mock import MagicMock

import pytest
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import Field


@pytest.fixture
def vectorstore(monkeypatch):
    """Import core.vectorstore with flashrank.Ranker faked out (module-level
    `_ranker = Ranker(...)` would otherwise load a real model on import)."""
    fake_flashrank = ModuleType("flashrank")
    fake_flashrank.Ranker = MagicMock(return_value=MagicMock())
    fake_flashrank.RerankRequest = lambda query, passages: {"query": query, "passages": passages}
    monkeypatch.setitem(sys.modules, "flashrank", fake_flashrank)
    sys.modules.pop("core.vectorstore", None)

    import core.vectorstore as module

    yield module

    sys.modules.pop("core.vectorstore", None)


def docs(*texts):
    return [Document(page_content=t) for t in texts]


class FakeRetriever(BaseRetriever):
    """A real BaseRetriever (not a MagicMock) - RerankingRetriever is a pydantic
    model whose base_retriever field is typed as BaseRetriever, so a bare mock
    fails validation."""

    docs_to_return: List[Document] = Field(default_factory=list)
    calls: List[str] = Field(default_factory=list)
    k: int = 4  # F18: BM25Retriever exposes a settable `k`; get_retriever() sets it to top_k

    def _get_relevant_documents(self, query, *, run_manager=None):
        self.calls.append(query)
        return self.docs_to_return


def test_rerank_documents_returns_empty_list_unchanged(vectorstore):
    assert vectorstore.rerank_documents("query", []) == []
    vectorstore._ranker.rerank.assert_not_called()


def test_rerank_documents_reorders_by_ranker_score(vectorstore):
    d = docs("irrelevant", "relevant", "somewhat relevant")
    # Ranker says doc 1 ("relevant") is the best match, then doc 2, then doc 0.
    vectorstore._ranker.rerank.return_value = [
        {"id": 1, "score": 0.9},
        {"id": 2, "score": 0.5},
        {"id": 0, "score": 0.1},
    ]

    result = vectorstore.rerank_documents("query", d, top_k=2)

    assert [doc.page_content for doc in result] == ["relevant", "somewhat relevant"]


def test_rerank_documents_respects_top_k(vectorstore):
    d = docs("a", "b", "c")
    vectorstore._ranker.rerank.return_value = [
        {"id": 0, "score": 0.9},
        {"id": 1, "score": 0.8},
        {"id": 2, "score": 0.7},
    ]

    result = vectorstore.rerank_documents("query", d, top_k=1)

    assert len(result) == 1
    assert result[0].page_content == "a"


def test_wrap_with_reranking_builds_retriever_with_given_top_k(vectorstore):
    base_retriever = FakeRetriever()

    wrapped = vectorstore.wrap_with_reranking(base_retriever, top_k=5)

    assert wrapped.base_retriever is base_retriever
    assert wrapped.top_k == 5


def test_reranking_retriever_reranks_base_retriever_results(vectorstore, monkeypatch):
    base_retriever = FakeRetriever(docs_to_return=docs("x", "y"))

    called = {}

    def fake_rerank(query, docs_in, top_k=3):
        called["query"] = query
        called["docs"] = docs_in
        called["top_k"] = top_k
        return docs_in[:top_k]

    monkeypatch.setattr(vectorstore, "rerank_documents", fake_rerank)
    retriever = vectorstore.wrap_with_reranking(base_retriever, top_k=1)

    result = retriever._get_relevant_documents("what's good?", run_manager=MagicMock())

    assert base_retriever.calls == ["what's good?"]
    assert called["query"] == "what's good?"
    assert called["top_k"] == 1
    assert len(result) == 1


@pytest.fixture
def patched_get_retriever(vectorstore, monkeypatch):
    """F18: stub every external boundary get_retriever() touches - PDF parsing, splitting, FAISS,
    and BM25 - so the fusion wiring can be tested without a real PDF, embeddings, or BM25 math.
    """
    split_docs = docs("chunk one", "chunk two")

    fake_loader = MagicMock()
    fake_loader.load.return_value = ["raw page"]
    monkeypatch.setattr(vectorstore, "PyPDFLoader", MagicMock(return_value=fake_loader))

    fake_splitter = MagicMock()
    fake_splitter.split_documents.return_value = split_docs
    monkeypatch.setattr(vectorstore, "RecursiveCharacterTextSplitter", MagicMock(return_value=fake_splitter))

    fake_vectorstore = MagicMock()
    fake_faiss_retriever = FakeRetriever()
    fake_vectorstore.as_retriever.return_value = fake_faiss_retriever
    fake_faiss_cls = MagicMock()
    fake_faiss_cls.load_local.return_value = fake_vectorstore
    fake_faiss_cls.from_documents.return_value = fake_vectorstore
    monkeypatch.setattr(vectorstore, "FAISS", fake_faiss_cls)

    fake_bm25_retriever = FakeRetriever()
    fake_bm25_cls = MagicMock()
    fake_bm25_cls.from_documents.return_value = fake_bm25_retriever
    monkeypatch.setattr(vectorstore, "BM25Retriever", fake_bm25_cls)

    fake_ensemble_cls = MagicMock(side_effect=lambda **kwargs: FakeRetriever())
    monkeypatch.setattr(vectorstore, "EnsembleRetriever", fake_ensemble_cls)

    return {
        "split_docs": split_docs,
        "faiss": fake_faiss_cls,
        "faiss_retriever": fake_faiss_retriever,
        "bm25": fake_bm25_cls,
        "bm25_retriever": fake_bm25_retriever,
        "ensemble": fake_ensemble_cls,
    }


def test_get_retriever_fuses_bm25_and_faiss_with_reranking(vectorstore, patched_get_retriever, monkeypatch):
    monkeypatch.setattr(vectorstore.os.path, "exists", lambda path: True)  # index already on disk

    result = vectorstore.get_retriever("italian", embeddings=MagicMock(), top_k=2)

    fakes = patched_get_retriever
    fakes["faiss"].load_local.assert_called_once()
    fakes["faiss"].from_documents.assert_not_called()  # already on disk - don't rebuild
    fakes["bm25"].from_documents.assert_called_once_with(fakes["split_docs"])  # F18: fed the same chunks
    assert fakes["bm25_retriever"].k == 2

    ensemble_kwargs = fakes["ensemble"].call_args.kwargs
    assert ensemble_kwargs["retrievers"] == [fakes["bm25_retriever"], fakes["faiss_retriever"]]
    assert ensemble_kwargs["weights"] == [0.5, 0.5]

    assert isinstance(result, vectorstore.RerankingRetriever)
    assert result.top_k == 2


def test_get_retriever_builds_and_saves_faiss_when_index_missing(vectorstore, patched_get_retriever, monkeypatch):
    monkeypatch.setattr(vectorstore.os.path, "exists", lambda path: False)
    fake_embeddings = MagicMock()

    vectorstore.get_retriever("mexican", embeddings=fake_embeddings, top_k=3)

    fakes = patched_get_retriever
    fakes["faiss"].load_local.assert_not_called()
    fakes["faiss"].from_documents.assert_called_once_with(fakes["split_docs"], fake_embeddings)
    fakes["faiss"].from_documents.return_value.save_local.assert_called_once()
