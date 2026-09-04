"""F6: In-code token & cost accounting for OpenAI calls. F9: step-latency tracing
(retriever vs LLM) and error-rate tracking. See FEATURES.md for the full writeup."""
import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Optional

from langchain_community.callbacks import get_openai_callback
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.tracers.context import register_configure_hook
from pydantic import BaseModel


# F6 In-Code Token & Cost Accounting
class UsageInfo(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    total_cost_usd: float


# F6 In-Code Token & Cost Accounting
def new_session_totals() -> dict:
    return {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "total_cost_usd": 0.0,
    }


# F6 In-Code Token & Cost Accounting
@contextmanager
def track_usage(session_totals: dict):
    """Wrap an LLM call, folding its token/cost stats into session_totals.

    Not thread-safe under concurrent requests (fine for this single-worker
    demo, not for a real multi-worker prod deployment).

    Usage:
        with track_usage(session_totals) as cb:
            result = chain.invoke(...)
        usage = UsageInfo(prompt_tokens=cb.prompt_tokens, ...)
    """
    with get_openai_callback() as cb:
        yield cb
    session_totals["prompt_tokens"] += cb.prompt_tokens
    session_totals["completion_tokens"] += cb.completion_tokens
    session_totals["total_tokens"] += cb.total_tokens
    session_totals["total_cost_usd"] += cb.total_cost


# F6 In-Code Token & Cost Accounting
def log_usage(cb, session_totals: dict, label: str = ""):
    """Print one call's usage plus the running session totals (CLI debug output)."""
    prefix = f"[F6] {label}".strip()
    print(f"\n{prefix} Tokens - prompt: {cb.prompt_tokens}, completion: {cb.completion_tokens}, "
          f"total: {cb.total_tokens} | Cost: ${cb.total_cost:.6f}")
    print(f"[F6] Session Total - prompt: {session_totals['prompt_tokens']}, "
          f"completion: {session_totals['completion_tokens']}, "
          f"total: {session_totals['total_tokens']} | "
          f"Cost: ${session_totals['total_cost_usd']:.6f}")


# F9 Observability & Tracing
class StepTimer(BaseCallbackHandler):
    """F9: records wall-clock latency for the retriever step and the LLM step of a
    single call, via LangChain's callback hooks. Set ambiently through
    step_timer_var below (the same trick get_openai_callback above uses), so it
    captures nested chain.invoke() calls even through Ephemeral Chat Memory (F7)'s
    wrapper, which doesn't forward `config` to the inner chain by hand.
    """

    def __init__(self):
        self.retriever_ms: float = 0.0
        self.llm_ms: float = 0.0
        self.total_ms: float = 0.0
        self._retriever_start: Optional[float] = None
        self._llm_start: Optional[float] = None

    def on_retriever_start(self, serialized, query, **kwargs):
        self._retriever_start = time.perf_counter()

    def on_retriever_end(self, documents, **kwargs):
        if self._retriever_start is not None:
            self.retriever_ms = (time.perf_counter() - self._retriever_start) * 1000

    def on_llm_start(self, serialized, prompts, **kwargs):
        self._llm_start = time.perf_counter()

    def on_llm_end(self, response, **kwargs):
        if self._llm_start is not None:
            self.llm_ms = (time.perf_counter() - self._llm_start) * 1000

    def on_chat_model_start(self, serialized, messages, **kwargs):
        # Chat models (e.g. ChatOpenAI) route through this hook instead of on_llm_start.
        self._llm_start = time.perf_counter()


step_timer_var: ContextVar[Optional[StepTimer]] = ContextVar("step_timer", default=None)
register_configure_hook(step_timer_var, True)


# F9 Observability & Tracing
def new_trace_totals() -> dict:
    return {"calls": 0, "errors": 0}


# F9 Observability & Tracing
@contextmanager
def trace_call(trace_totals: dict):
    """F9: wraps one call, yielding a StepTimer that fills in with retriever/LLM
    latency once the wrapped chain.invoke() finishes, and folding call/error
    counts into trace_totals.

    Not thread-safe under concurrent requests - same caveat as track_usage above.

    Usage:
        with trace_call(trace_totals) as timer:
            result = chain.invoke(...)
        # timer.retriever_ms / timer.llm_ms / timer.total_ms now populated
    """
    timer = StepTimer()
    step_timer_var.set(timer)
    trace_totals["calls"] += 1
    start = time.perf_counter()
    try:
        yield timer
    except Exception:
        trace_totals["errors"] += 1
        raise
    finally:
        timer.total_ms = (time.perf_counter() - start) * 1000
        step_timer_var.set(None)


# F9 Observability & Tracing
def log_trace(timer: StepTimer, trace_totals: dict, label: str = ""):
    """Print one call's step-latency breakdown plus the running error rate (CLI debug output)."""
    prefix = f"[F9] {label}".strip()
    error_rate = (trace_totals["errors"] / trace_totals["calls"] * 100) if trace_totals["calls"] else 0.0
    print(f"\n{prefix} Latency - retriever: {timer.retriever_ms:.1f}ms, llm: {timer.llm_ms:.1f}ms, "
          f"total: {timer.total_ms:.1f}ms")
    print(f"[F9] Error Rate - {trace_totals['errors']}/{trace_totals['calls']} calls ({error_rate:.1f}%)")
