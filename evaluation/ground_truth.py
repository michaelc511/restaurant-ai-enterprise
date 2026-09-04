# F17: loads the fixed ground-truth question/answer pairs each cuisine's eval run scores
# against - plain JSON fixture data, checked into the repo like test fixtures, not
# regenerated per run, so a score change means the system changed, not the test.
import json
from pathlib import Path
from typing import TypedDict

FIXTURES_DIR = Path(__file__).parent / "fixtures"  # F17: one JSON file per cuisine
CUISINES = ["sushi", "steak", "italian"]  # F12: same set as engines/plain_rag_engine.py's AVAILABLE_CUISINES


class EvalCase(TypedDict):
    question: str
    expected_answer: str


def load_ground_truth(cuisine: str) -> list[EvalCase]:
    """F17: one cuisine's fixed test questions + known-good answers, read from
    evaluation/fixtures/<cuisine>.json."""
    path = FIXTURES_DIR / f"{cuisine}.json"
    with open(path) as f:
        return json.load(f)
