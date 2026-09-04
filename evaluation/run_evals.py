# F17: Automated RAG Evals Harness - runs every ground-truth question through the same
# engines.base.get_engine(...) production factory Modular Engine Strategy Factory (F12) uses,
# scores each answer against faithfulness/answer_relevancy/context_precision (evaluation/scoring.py),
# and reports a single pass/fail number - the same shape as a pytest exit code, so CI/CD Eval
# Regression Gate (F20) can gate a pull request on it the same way it already gates on `pytest`
# failing.
#
# Usage:
#   python -m evaluation.run_evals
#   python -m evaluation.run_evals --cuisine sushi
#   python -m evaluation.run_evals --engine langgraph
import argparse
import sys
import uuid

from dotenv import find_dotenv, load_dotenv

from core.llm import build_llm_and_embeddings  # F2/F12: same provider selection as every engine
from engines.base import get_engine  # F12
from evaluation.ground_truth import CUISINES, load_ground_truth
from evaluation.scoring import EvalScore, score_answer

load_dotenv(find_dotenv())


def run(engine_name: str, cuisines: list[str]) -> list[EvalScore]:
    engine = get_engine(engine_name)  # F12: the same factory production traffic hits
    judge_llm, _ = build_llm_and_embeddings()  # a separate LLM call from the answering engine's own, so the judge never grades its own homework's raw client state
    session_id = f"eval-{uuid.uuid4()}"  # one throwaway session per run

    results = []
    for cuisine in cuisines:
        for case in load_ground_truth(cuisine):
            # use_memory=False: each fixture question is graded independently - conversation
            # memory carrying over between unrelated fixture questions would make a score change
            # mean "the memory state drifted", not "the system changed" (see evaluation/ground_truth.py).
            response = engine.answer(cuisine, case["question"], session_id, use_memory=False)
            answer = response["result"]
            context = "\n\n".join(doc.page_content for doc in response["source_documents"])

            faithfulness, answer_relevancy, context_precision = score_answer(
                judge_llm, case["question"], answer, context
            )
            results.append(EvalScore(
                question=case["question"],
                answer=answer,
                faithfulness=faithfulness,
                answer_relevancy=answer_relevancy,
                context_precision=context_precision,
            ))
    return results


def report(results: list[EvalScore]) -> bool:
    """Prints a per-question breakdown (reasoning only for failures) and the pass/fail summary
    line CI/CD Eval Regression Gate (F20) is meant to key off of. Returns True iff every
    question passed."""
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"[{status}] {r.question}")
        print(
            f"    faithfulness={r.faithfulness.score:.2f}  "
            f"answer_relevancy={r.answer_relevancy.score:.2f}  "
            f"context_precision={r.context_precision.score:.2f}"
        )
        if not r.passed:
            for name, judgment in (
                ("faithfulness", r.faithfulness),
                ("answer_relevancy", r.answer_relevancy),
                ("context_precision", r.context_precision),
            ):
                print(f"      {name}: {judgment.reasoning}")

    passed = sum(1 for r in results if r.passed)
    print(f"\n{passed}/{len(results)} passed")
    return passed == len(results)


def main():
    parser = argparse.ArgumentParser(description="F17: run the RAG eval suite against the checked-in ground-truth fixtures.")
    parser.add_argument("--engine", default="plain_rag", choices=["plain_rag", "langgraph"])
    parser.add_argument(
        "--cuisine", action="append", dest="cuisines", choices=CUISINES,
        help="repeatable (e.g. --cuisine sushi --cuisine steak); defaults to all cuisines",
    )
    args = parser.parse_args()

    results = run(args.engine, args.cuisines or CUISINES)
    all_passed = report(results)
    sys.exit(0 if all_passed else 1)  # non-zero exit on any failing question - what F20 gates a PR on


if __name__ == "__main__":
    main()
