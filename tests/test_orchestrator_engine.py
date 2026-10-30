"""F23-style unit tests for F13's orchestrator multi-agent engine - engines/orchestrator_engine.py -
with the LLM, retriever, and Google Sheet all mocked out so tests run with no API key and no network.
The MCP Tools agent talks to the real api/mcp_server.py over MCP's in-memory transport - only the
sheet reads underneath it are mocked.
"""
from unittest.mock import MagicMock

import pytest
from langchain_core.documents import Document
from langchain_core.messages import AIMessage

import api.mcp_server as mcp_server
import engines.orchestrator_engine as orch
from core.guardrails import IntentClassification, OFF_TOPIC_MESSAGE
from core.sanitize import CONTEXT_START


def fake_llm(intent="menu", use_menu=True, use_live_data=False, grounded=True, tool_calls=None):
    """A fake LLM that answers each structured-output schema the engine asks for, plus bind_tools()
    for the MCP agent and a plain invoke() for synthesis."""
    llm = MagicMock()
    by_schema = {
        IntentClassification: IntentClassification(intent=intent, reasoning="because"),
        orch.OrchestratorPlan: orch.OrchestratorPlan(use_menu=use_menu, use_live_data=use_live_data, reasoning="plan"),
        orch.VerifyDecision: orch.VerifyDecision(grounded=grounded, reasoning="missing price"),
    }

    def with_structured_output(schema):
        structured = MagicMock()
        structured.invoke.return_value = by_schema[schema]
        return structured

    llm.with_structured_output.side_effect = with_structured_output
    llm.bind_tools.return_value.invoke.return_value = AIMessage(content="", tool_calls=tool_calls or [])
    llm.invoke.return_value = AIMessage(content="final answer")
    return llm


@pytest.fixture
def build_engine(monkeypatch):
    """Builds an OrchestratorEngine around the given fake LLM, with a mocked retriever per cuisine."""
    def _build(llm):
        retriever = MagicMock()
        retriever.invoke.return_value = [Document(page_content="menu chunk")]
        monkeypatch.setattr(orch, "build_llm_and_embeddings", lambda: (llm, MagicMock()))
        monkeypatch.setattr(orch, "get_retriever", lambda cuisine, embeddings: retriever)
        engine = orch.OrchestratorEngine()
        return engine, retriever
    return _build


def test_off_topic_question_is_redirected_without_planning_or_retrieval(build_engine):
    llm = fake_llm(intent="off_topic")
    engine, retriever = build_engine(llm)

    result = engine.answer("sushi", "Who won the World Cup?", "s1", use_memory=False)

    assert result == {"result": OFF_TOPIC_MESSAGE, "source_documents": []}
    retriever.invoke.assert_not_called()
    llm.bind_tools.assert_not_called()


def test_menu_only_plan_uses_the_menu_agent_and_skips_tools(build_engine):
    llm = fake_llm(use_menu=True, use_live_data=False)
    engine, retriever = build_engine(llm)

    result = engine.answer("sushi", "What's in the Dragon Roll?", "s1", use_memory=False)

    assert result["result"] == "final answer"
    assert [d.page_content for d in result["source_documents"]] == ["menu chunk"]
    retriever.invoke.assert_called_once()
    llm.bind_tools.assert_not_called()


def test_live_data_plan_calls_the_chosen_tool_and_sanitizes_its_output(build_engine, monkeypatch):
    monkeypatch.setattr(mcp_server, "get_daily_specials", lambda day: [{"Dish Name": "Test Special", "Day": day}])
    llm = fake_llm(use_menu=False, use_live_data=True,
                   tool_calls=[{"name": "daily_specials", "args": {"day": "Fri"}, "id": "c1"}])
    engine, retriever = build_engine(llm)

    result = engine.answer("sushi", "Any specials Friday?", "s1", use_memory=False)

    retriever.invoke.assert_not_called()
    [live_doc] = result["source_documents"]
    assert live_doc.metadata == {"source": "mcp_tools"}
    assert live_doc.page_content.startswith(CONTEXT_START)  # F22: tool output is delimiter-isolated
    assert "Test Special" in live_doc.page_content


def test_both_specialists_run_when_the_plan_needs_both(build_engine, monkeypatch):
    monkeypatch.setattr(mcp_server, "get_hours_and_events", lambda target_date: [{"Status": "Closed"}])
    llm = fake_llm(use_menu=True, use_live_data=True,
                   tool_calls=[{"name": "hours_and_events", "args": {"target_date": "2026-12-25"}, "id": "c1"}])
    engine, retriever = build_engine(llm)

    result = engine.answer("steak", "Are you open Christmas, and do you have ribeye?", "s1", use_memory=False)

    retriever.invoke.assert_called_once()
    sources = [d.metadata.get("source") for d in result["source_documents"]]
    assert sources == [None, "mcp_tools"]  # menu chunks first, then live data


def test_unknown_tool_name_is_skipped(build_engine):
    llm = fake_llm(use_menu=False, use_live_data=True,
                   tool_calls=[{"name": "delete_everything", "args": {}, "id": "c1"}])
    engine, _ = build_engine(llm)

    result = engine.answer("sushi", "Any specials?", "s1", use_memory=False)

    assert result["source_documents"] == []


def test_sheet_failure_is_reported_as_unavailable_not_raised(build_engine, monkeypatch):
    def broken(day):
        raise RuntimeError("sheet down")
    monkeypatch.setattr(mcp_server, "get_daily_specials", broken)
    llm = fake_llm(use_menu=False, use_live_data=True,
                   tool_calls=[{"name": "daily_specials", "args": {}, "id": "c1"}])
    engine, _ = build_engine(llm)

    result = engine.answer("sushi", "Any specials?", "s1", use_memory=False)

    content = result["source_documents"][0].page_content
    assert "unavailable (" in content and "sheet down" in content


def test_empty_plan_falls_back_to_the_menu_agent(build_engine):
    llm = fake_llm(use_menu=False, use_live_data=False)
    engine, retriever = build_engine(llm)

    engine.answer("italian", "Do you have tiramisu?", "s1", use_memory=False)

    retriever.invoke.assert_called_once()


def test_ungrounded_answer_retries_synthesis_at_most_max_retries_times(build_engine):
    llm = fake_llm(grounded=False)
    engine, retriever = build_engine(llm)

    engine.answer("sushi", "What's in the Dragon Roll?", "s1", use_memory=False)

    assert llm.invoke.call_count == orch.MAX_RETRIES  # one synthesis per verify attempt
    retriever.invoke.assert_called_once()  # retries re-synthesize, they don't re-retrieve


def test_tools_are_discovered_from_the_mcp_server(build_engine):
    engine, _ = build_engine(fake_llm())

    assert engine.mcp_tool_names == {"daily_specials", "hours_and_events", "org_directory", "company_items"}
    specials = next(t for t in engine.mcp_tools if t["function"]["name"] == "daily_specials")
    assert "day" in specials["function"]["parameters"]["properties"]


def test_unknown_cuisine_raises(build_engine):
    engine, _ = build_engine(fake_llm())

    with pytest.raises(ValueError):
        engine.answer("thai", "anything", "s1")
