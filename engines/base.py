# F12: Modular Engine Strategy Factory - the shared plug/socket every "engine" (plain RAG today,
# LangGraph/CrewAI/AutoGen later) implements the same way, so callers never depend on a concrete
# engine class directly - only on this interface and the factory below.
from abc import ABC, abstractmethod


class BaseMenuEngine(ABC):  # F12: common interface every engine implements
    @abstractmethod
    def answer(self, cuisine: str, question: str, session_id: str, use_memory: bool = True) -> dict:
        """Returns {"result": str, "source_documents": [Document, ...]} - same shape RetrievalQA.invoke() returns."""


_engine_instances: dict[str, BaseMenuEngine] = {}  # F12: cached singletons, keyed by engine name - built once, reused


def get_engine(name: str) -> BaseMenuEngine:  # F12: factory - returns the requested engine, building it on first use
    if name not in _engine_instances:
        if name == "plain_rag":
            from engines.plain_rag_engine import PlainRagEngine  # lazy import - avoids a hard dependency at module load
            _engine_instances[name] = PlainRagEngine()
        elif name == "langgraph":  # F13
            from engines.langgraph_engine import LangGraphEngine  # lazy import - avoids a hard dependency at module load
            _engine_instances[name] = LangGraphEngine()
        else:
            raise ValueError(f"Unknown engine: {name}")
    return _engine_instances[name]
