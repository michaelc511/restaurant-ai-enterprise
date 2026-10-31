# F19: Query Guardrails & Intent Gating - a structured classifier that labels each question's
# intent up front, so an off-topic question gets a consistent, measurable rejection instead of
# either burning a retrieval + generation call on something no menu chunk could ever answer, or
# falling through core.sheets.detect_ops_intent() (F8)'s keyword heuristic, which only recognizes
# specials/hours phrasing and has no concept of "off-topic" at all. Same
# llm.with_structured_output(...) judging pattern Automated RAG Evaluation Suite (F17)'s
# evaluation/scoring.py already uses - no new dependency.
from typing import Literal

from pydantic import BaseModel, Field

from core.domain import domain  # F12

OFF_TOPIC_MESSAGE = domain.OFF_TOPIC_MESSAGE  # F12: re-exported - menu_api.py and engines import it from here


class IntentClassification(BaseModel):  # F19: one classification call's structured output
    intent: Literal[domain.INTENT_LABELS] = Field(  # F12: the domain's labels
        description=domain.INTENT_DESCRIPTION  # F12
    )
    reasoning: str = Field(description="one short sentence justifying the label")


INTENT_PROMPT = domain.INTENT_PROMPT  # F12


def classify_intent(llm, question: str) -> IntentClassification:
    """F19: one structured LLM call labeling `question`'s intent. Callers run this before the RAG
    chain (menu_api.py) / engine (engine_api.py) ever run, so an off_topic question never reaches
    retrieval or generation - the tradeoff being one extra LLM call added to every request,
    on-topic ones included."""
    return llm.with_structured_output(IntentClassification).invoke(
        INTENT_PROMPT.format(question=question)
    )


def is_off_topic(classification: IntentClassification) -> bool:
    return classification.intent == "off_topic"
