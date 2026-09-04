# F17: LLM-judge scoring for the three RAG-quality metrics the eval harness reports -
# faithfulness, answer relevancy, and context precision. The checklist names Ragas/DeepEval
# for this; both were evaluated and rejected for this repo specifically - `pip install ragas`
# here backtracks onto openai 3.3.1 -> 1.109.1 and langchain-openai 1.6.0 -> 1.1.9 to satisfy
# its pin range, a downgrade that would break every other engine sharing this venv (core/llm.py,
# engines/plain_rag_engine.py, engines/langgraph_engine.py all depend on the current versions).
# This scores the same three axes with the LLM already wired up via core.llm, using the same
# structured-output judging pattern LangGraph State Machine Engine (F13)'s route/verify nodes
# already use (`llm.with_structured_output(...)`) - no new dependency, no version conflict.
from pydantic import BaseModel, Field

FAITHFULNESS_THRESHOLD = 0.8
ANSWER_RELEVANCY_THRESHOLD = 0.8
CONTEXT_PRECISION_THRESHOLD = 0.6  # some retrieved-but-unused noise is tolerated; F10 re-ranking still narrows to top_k=3


class MetricJudgment(BaseModel):  # F17: one judge call's structured output
    score: float = Field(ge=0.0, le=1.0, description="0.0 = completely fails the metric, 1.0 = fully satisfies it")
    reasoning: str = Field(description="one or two sentences justifying the score")


class EvalScore(BaseModel):  # F17: one scored question, rolled up into a single pass/fail
    question: str
    answer: str
    faithfulness: MetricJudgment
    answer_relevancy: MetricJudgment
    context_precision: MetricJudgment

    @property
    def passed(self) -> bool:
        return (
            self.faithfulness.score >= FAITHFULNESS_THRESHOLD
            and self.answer_relevancy.score >= ANSWER_RELEVANCY_THRESHOLD
            and self.context_precision.score >= CONTEXT_PRECISION_THRESHOLD
        )


FAITHFULNESS_PROMPT = """You are grading a restaurant assistant's answer for FAITHFULNESS: does every claim in
the answer actually appear in, or follow directly from, the retrieved context below? An answer that adds a
detail not present in the context - a price, an ingredient, a policy - is unfaithful, even if that detail
happens to be true in general.

Retrieved context:
----------------
{context}
----------------
Answer to grade:
{answer}

Score 1.0 if every claim is grounded in the context, 0.0 if the answer invents something not in it, or a
value in between if only part of the answer is unsupported."""

ANSWER_RELEVANCY_PROMPT = """You are grading a restaurant assistant's answer for ANSWER RELEVANCY: does it
actually address what was asked, without padding, going off-topic, or answering a different question?

Question: {question}
Answer: {answer}

Score 1.0 if the answer directly and completely addresses the question, 0.0 if it doesn't address it at all,
or a value in between for a partial/tangential answer."""

CONTEXT_PRECISION_PROMPT = """You are grading a RAG system's retrieval for CONTEXT PRECISION: of the chunks
retrieved below, how many were actually useful for answering the question - as opposed to irrelevant chunks
that just added noise?

Question: {question}
Retrieved context:
----------------
{context}
----------------

Score 1.0 if every retrieved chunk was relevant and useful, 0.0 if none were, or a value in between for a
mix of useful and irrelevant chunks."""


def _judge(llm, prompt_template: str, **kwargs) -> MetricJudgment:
    return llm.with_structured_output(MetricJudgment).invoke(prompt_template.format(**kwargs))


def score_answer(llm, question: str, answer: str, context: str) -> tuple[MetricJudgment, MetricJudgment, MetricJudgment]:
    """F17: runs all three judge calls for one answered question, returning
    (faithfulness, answer_relevancy, context_precision)."""
    faithfulness = _judge(llm, FAITHFULNESS_PROMPT, context=context, answer=answer)
    answer_relevancy = _judge(llm, ANSWER_RELEVANCY_PROMPT, question=question, answer=answer)
    context_precision = _judge(llm, CONTEXT_PRECISION_PROMPT, question=question, context=context)
    return faithfulness, answer_relevancy, context_precision
