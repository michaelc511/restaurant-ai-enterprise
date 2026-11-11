# F9: LangSmith run names and tags - one clear run name per engine flow instead of LangGraph's
# default "LangGraph"/"RunnableSequence", plus tags (engine, cuisine, model, prompt version,
# environment) so traces can be filtered in LangSmith. LLM calls and retrievers are already traced
# by LangChain itself; this only labels the top-level run. Pure config - if LangSmith is off or
# unreachable, LangChain ignores it and the request still answers.
import os

PROMPT_VERSION = "v1"  # F9: bump when RAG/agent prompts change, so traces can be compared by version


def _model_name(llm: object) -> str:  # F9: ChatOpenAI has model_name, AzureChatOpenAI deployment_name
    for attr in ("model_name", "deployment_name"):
        value = getattr(llm, attr, None)
        if isinstance(value, str) and value:
            return value
    return "unknown"


def _environment() -> str:  # F9: Fly sets FLY_APP_NAME on every machine
    return "prod" if os.environ.get("FLY_APP_NAME") else "local"


# F9: merged into base so F7's memory config (session_id) keeps working alongside the run name/tags
def trace_config(run_name: str, cuisine: str, llm: object, base: dict | None = None) -> dict:
    model = _model_name(llm)
    env = _environment()
    config = dict(base or {})
    config["run_name"] = run_name
    config["tags"] = [f"cuisine:{cuisine}", f"model:{model}", f"prompt:{PROMPT_VERSION}", f"env:{env}"]
    config["metadata"] = {"cuisine": cuisine, "model": model, "prompt_version": PROMPT_VERSION, "env": env}
    return config
