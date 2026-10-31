# F17: loads the fixed ground-truth question/answer pairs each cuisine's eval run scores
# against - plain JSON fixture data, checked into the repo like test fixtures, not
# regenerated per run, so a score change means the system changed, not the test.
import json
from pathlib import Path
from typing import TypedDict

from core.domain import domain  # F12

FIXTURES_DIR = domain.EVALS_DIR  # F17/F12: one JSON file per cuisine, in the active domain pack
CUISINES = domain.COLLECTIONS  # F12: from the active domain pack


class EvalCase(TypedDict):
    question: str
    expected_answer: str


def load_ground_truth(cuisine: str) -> list[EvalCase]:
    """F17: one cuisine's fixed test questions + known-good answers, read from
    domains/<DOMAIN>/evals/<cuisine>.json."""
    path = FIXTURES_DIR / f"{cuisine}.json"
    with open(path) as f:
        return json.load(f)
