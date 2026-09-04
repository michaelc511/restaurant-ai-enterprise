"""F23-style unit tests for F17's evaluation package - scoring.py's judge logic and
ground_truth.py's fixture loader, with the LLM judge mocked out so tests run with no
API key and no network.
"""
from unittest.mock import MagicMock

from evaluation.ground_truth import CUISINES, load_ground_truth
from evaluation.scoring import (
    ANSWER_RELEVANCY_THRESHOLD,
    CONTEXT_PRECISION_THRESHOLD,
    FAITHFULNESS_THRESHOLD,
    EvalScore,
    MetricJudgment,
    score_answer,
)


def fake_llm(*scores):
    """A fake LLM whose with_structured_output(...).invoke(...) yields each of `scores`
    in turn, in the order score_answer() calls the judge: faithfulness, answer_relevancy,
    context_precision."""
    llm = MagicMock()
    structured = MagicMock()
    structured.invoke.side_effect = [MetricJudgment(score=s, reasoning=f"score {s}") for s in scores]
    llm.with_structured_output.return_value = structured
    return llm


def test_score_answer_returns_the_three_judgments_in_order():
    llm = fake_llm(0.9, 0.8, 0.7)

    faithfulness, answer_relevancy, context_precision = score_answer(
        llm, "What rolls do you have?", "The Dragon Roll.", "Dragon Roll ($18.50) - BBQ eel..."
    )

    assert faithfulness.score == 0.9
    assert answer_relevancy.score == 0.8
    assert context_precision.score == 0.7


def test_score_answer_calls_with_structured_output_using_the_metric_judgment_schema():
    llm = fake_llm(1.0, 1.0, 1.0)

    score_answer(llm, "q", "a", "c")

    assert llm.with_structured_output.call_count == 3
    for call in llm.with_structured_output.call_args_list:
        assert call.args == (MetricJudgment,)


def _score(faithfulness, answer_relevancy, context_precision) -> EvalScore:
    return EvalScore(
        question="q",
        answer="a",
        faithfulness=MetricJudgment(score=faithfulness, reasoning=""),
        answer_relevancy=MetricJudgment(score=answer_relevancy, reasoning=""),
        context_precision=MetricJudgment(score=context_precision, reasoning=""),
    )


def test_eval_score_passes_when_every_metric_meets_its_threshold():
    score = _score(FAITHFULNESS_THRESHOLD, ANSWER_RELEVANCY_THRESHOLD, CONTEXT_PRECISION_THRESHOLD)

    assert score.passed is True


def test_eval_score_fails_when_faithfulness_is_below_threshold():
    score = _score(FAITHFULNESS_THRESHOLD - 0.01, 1.0, 1.0)

    assert score.passed is False


def test_eval_score_fails_when_answer_relevancy_is_below_threshold():
    score = _score(1.0, ANSWER_RELEVANCY_THRESHOLD - 0.01, 1.0)

    assert score.passed is False


def test_eval_score_fails_when_context_precision_is_below_threshold():
    score = _score(1.0, 1.0, CONTEXT_PRECISION_THRESHOLD - 0.01)

    assert score.passed is False


def test_load_ground_truth_reads_each_cuisines_fixture_file():
    for cuisine in CUISINES:
        cases = load_ground_truth(cuisine)

        assert len(cases) > 0
        for case in cases:
            assert case["question"]
            assert case["expected_answer"]
