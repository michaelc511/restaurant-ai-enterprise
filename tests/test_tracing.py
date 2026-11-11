"""F9 unit tests for core/tracing.py - LangSmith run names and tags. No network, no API key."""
from unittest.mock import MagicMock

import core.tracing as tracing


class FakeOpenAI:
    model_name = "gpt-4o-mini"


class FakeAzure:
    deployment_name = "gpt-5-mini"


def test_trace_config_sets_name_tags_and_metadata(monkeypatch):
    monkeypatch.delenv("FLY_APP_NAME", raising=False)
    config = tracing.trace_config("menu-langgraph", "sushi", FakeOpenAI())
    assert config["run_name"] == "menu-langgraph"
    assert config["tags"] == ["cuisine:sushi", "model:gpt-4o-mini", f"prompt:{tracing.PROMPT_VERSION}", "env:local"]
    assert config["metadata"]["env"] == "local"


def test_env_is_prod_on_fly(monkeypatch):
    monkeypatch.setenv("FLY_APP_NAME", "restaurant-ai-platform")
    assert "env:prod" in tracing.trace_config("x", "steak", FakeOpenAI())["tags"]


def test_azure_model_name_and_unknown_fallback():
    assert "model:gpt-5-mini" in tracing.trace_config("x", "steak", FakeAzure())["tags"]
    assert "model:unknown" in tracing.trace_config("x", "steak", MagicMock())["tags"]  # mocks aren't str


def test_base_config_is_kept_and_not_mutated():
    base = {"configurable": {"session_id": "italian:s1"}}
    config = tracing.trace_config("x", "italian", FakeOpenAI(), base)
    assert config["configurable"] == {"session_id": "italian:s1"}
    assert "run_name" not in base
