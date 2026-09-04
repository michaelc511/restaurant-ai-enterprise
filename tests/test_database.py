"""F23: unit tests for core/database.py - usage_log persistence and totals."""
import sqlite3

import pytest

from core.database import get_session_totals, init_db, log_call
from core.telemetry import UsageInfo


def make_usage(prompt=10, completion=5, total=15, cost=0.001):
    return UsageInfo(
        prompt_tokens=prompt, completion_tokens=completion, total_tokens=total, total_cost_usd=cost
    )


def test_init_db_creates_usage_log_table(tmp_path):
    db_path = str(tmp_path / "usage.db")
    init_db(db_path)

    conn = sqlite3.connect(db_path)
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    conn.close()

    assert ("usage_log",) in tables


def test_init_db_is_idempotent(tmp_path):
    db_path = str(tmp_path / "usage.db")
    init_db(db_path)
    init_db(db_path)  # must not raise on an already-existing table


def test_get_session_totals_for_unknown_session_returns_zeros_not_error(tmp_path):
    db_path = str(tmp_path / "usage.db")
    init_db(db_path)

    totals = get_session_totals("never-logged-session", db_path)

    assert totals == {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "total_cost_usd": 0.0,
    }


def test_log_call_persists_a_row(tmp_path):
    db_path = str(tmp_path / "usage.db")
    init_db(db_path)

    log_call("italian", "session-1", "what's the special?", make_usage(), db_path)

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT cuisine, session_id, question, prompt_tokens, completion_tokens, total_tokens, cost_usd "
        "FROM usage_log"
    ).fetchone()
    conn.close()

    assert row == ("italian", "session-1", "what's the special?", 10, 5, 15, 0.001)


def test_get_session_totals_sums_multiple_calls_in_same_session(tmp_path):
    db_path = str(tmp_path / "usage.db")
    init_db(db_path)

    log_call("italian", "session-1", "q1", make_usage(10, 5, 15, 0.001), db_path)
    log_call("italian", "session-1", "q2", make_usage(20, 8, 28, 0.002), db_path)

    totals = get_session_totals("session-1", db_path)

    assert totals["prompt_tokens"] == 30
    assert totals["completion_tokens"] == 13
    assert totals["total_tokens"] == 43
    assert totals["total_cost_usd"] == pytest.approx(0.003)


def test_get_session_totals_does_not_leak_across_sessions(tmp_path):
    db_path = str(tmp_path / "usage.db")
    init_db(db_path)

    log_call("italian", "session-1", "q1", make_usage(10, 5, 15, 0.001), db_path)
    log_call("sushi", "session-2", "q1", make_usage(100, 50, 150, 0.01), db_path)

    totals = get_session_totals("session-1", db_path)

    assert totals["prompt_tokens"] == 10
    assert totals["total_tokens"] == 15
