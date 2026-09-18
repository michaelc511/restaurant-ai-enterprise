"""F23-style unit tests for F19's intent classifier - core/guardrails.py - with the LLM
mocked out so tests run with no API key and no network.
"""
from unittest.mock import MagicMock

from core.guardrails import IntentClassification, classify_intent, is_off_topic


def fake_llm(intent: str, reasoning: str = "because"):
    """A fake LLM whose with_structured_output(...).invoke(...) returns a single
    IntentClassification, mirroring evaluation/scoring.py's fake_llm test helper."""
    llm = MagicMock()
    structured = MagicMock()
    structured.invoke.return_value = IntentClassification(intent=intent, reasoning=reasoning)
    llm.with_structured_output.return_value = structured
    return llm


def test_classify_intent_returns_the_llms_classification():
    llm = fake_llm("menu", "asks about a dish")

    result = classify_intent(llm, "What's in the Dragon Roll?")

    assert result.intent == "menu"
    assert result.reasoning == "asks about a dish"


def test_classify_intent_calls_with_structured_output_using_the_intent_schema():
    llm = fake_llm("hours")

    classify_intent(llm, "Are you open Sunday?")

    llm.with_structured_output.assert_called_once_with(IntentClassification)


def test_is_off_topic_true_for_off_topic_intent():
    assert is_off_topic(IntentClassification(intent="off_topic", reasoning="")) is True


def test_is_off_topic_false_for_on_topic_intents():
    for intent in ("menu", "specials", "hours"):
        assert is_off_topic(IntentClassification(intent=intent, reasoning="")) is False
