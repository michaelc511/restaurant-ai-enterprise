"""F7: Ephemeral in-memory chat history per session, using RunnableWithMessageHistory.
F16: adds a persistent, SQLite-backed alternative via MEMORY_BACKEND, so a session's
history can survive a server restart instead of living only in RAM.

MEMORY_BACKEND=ephemeral (default) - histories live in a module-level dict, never
touch disk, and reset whenever the process restarts.
MEMORY_BACKEND=persistent - histories are written to a SQLite file (CHAT_HISTORY_DB_PATH)
via SQLChatMessageHistory, surviving a restart or crash.

Either way, each session's history is trimmed to the last MAX_HISTORY_TURNS exchanges
right before it's rendered into the prompt, to bound context-window token overhead -
the stored history itself is never truncated, only what gets sent to the LLM.
"""
import os

from langchain_community.chat_message_histories import ChatMessageHistory, SQLChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.runnables import RunnableLambda
from langchain_core.runnables.history import RunnableWithMessageHistory

DEBUG_MODE = os.environ.get("DEBUG_MODE", "true").lower() != "false"
MEMORY_BACKEND = os.environ.get("MEMORY_BACKEND", "ephemeral").lower()  # F16: "ephemeral" (F7, RAM) or "persistent" (F16, SQLite)
CHAT_HISTORY_DB_PATH = "chat_history.db"  # F16: only used when MEMORY_BACKEND=persistent

MAX_HISTORY_TURNS = 5  # working context window - keep only the last N exchanges

_session_histories: dict[str, ChatMessageHistory] = {}  # F7: ephemeral, in-memory, resets on restart


def get_session_history(session_id: str) -> BaseChatMessageHistory:
    if MEMORY_BACKEND == "persistent":  # F16: durable, survives a restart/crash
        return SQLChatMessageHistory(session_id=session_id, connection=f"sqlite:///{CHAT_HISTORY_DB_PATH}")
    if session_id not in _session_histories:  # F7: ephemeral (default) - in-memory, resets on restart
        _session_histories[session_id] = ChatMessageHistory()
    return _session_histories[session_id]


def _render_history(messages: list) -> str:
    if not messages:
        return ""
    trimmed = messages[-MAX_HISTORY_TURNS * 2:]  # F16: trim on render, not on storage - full history stays intact either way
    lines = [f"{'User' if m.type == 'human' else 'Assistant'}: {m.content}" for m in trimmed]
    return "Previous conversation:\n" + "\n".join(lines) + "\n\n"


def wrap_with_memory(ask_fn) -> RunnableWithMessageHistory:
    """Wrap ask_fn (question: str -> {"result": ..., "source_documents": ...})
    so multi-turn context is prepended to the question automatically, and each
    exchange is recorded into that session's history afterward.

    Usage:
        chain = wrap_with_memory(lambda q: qa_chain.invoke({"query": q}))
        chain.invoke({"query": "..."}, config={"configurable": {"session_id": "sushi:default"}})
    """

    def _invoke(input: dict, config: dict) -> dict:
        history_context = _render_history(input.get("history", []))
        contextualized_query = history_context + input["query"]
        if DEBUG_MODE and history_context:  # F7: show what memory injected, only when there's something to show
            print(f"\n[F7] Contextualized query sent to the chain:\n{contextualized_query}")
        return ask_fn(contextualized_query)

    runnable = RunnableLambda(_invoke)
    return RunnableWithMessageHistory(
        runnable,
        get_session_history,
        input_messages_key="query",
        history_messages_key="history",
        output_messages_key="result",
    )
