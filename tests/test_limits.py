# F21: usage limits - per-visitor rate limit and daily OpenAI budget. Fully mocked: temp SQLite, no API key.
import importlib
import sqlite3
from datetime import datetime, timezone

import pytest

from core import limits


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    limits.reset()
    for name in ("RATE_LIMIT_PER_MINUTE", "RATE_LIMIT_PER_DAY", "DAILY_BUDGET_USD"):
        monkeypatch.delenv(name, raising=False)
    yield
    limits.reset()


def _usage_db(tmp_path, rows: list[tuple[str, float]]) -> str:
    path = str(tmp_path / "usage.db")
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE usage_log (timestamp TEXT, cost_usd REAL)")
    conn.executemany("INSERT INTO usage_log VALUES (?, ?)", rows)
    conn.commit()
    conn.close()
    return path


def test_per_minute_limit_blocks_the_sixth_call_by_default():
    for i in range(5):
        limits.check_rate("1.1.1.1", now=1000.0 + i)
    with pytest.raises(limits.LimitExceeded, match="5 a minute"):
        limits.check_rate("1.1.1.1", now=1006.0)
    limits.check_rate("2.2.2.2", now=1006.0)  # another visitor is not affected
    limits.check_rate("1.1.1.1", now=1070.0)  # a minute later the window has moved on


def test_daily_limit_and_expiry(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_DAY", "3")
    for i in range(3):
        limits.check_rate("ip", now=1000.0 + i * 120)
    with pytest.raises(limits.LimitExceeded, match="Daily limit of 3"):
        limits.check_rate("ip", now=2000.0)
    limits.check_rate("ip", now=1000.0 + 86400 + 1)


def test_zero_switches_the_rate_limit_off(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "0")
    monkeypatch.setenv("RATE_LIMIT_PER_DAY", "0")
    for i in range(20):
        limits.check_rate("ip", now=1000.0 + i)


def test_budget_counts_only_today(tmp_path, monkeypatch):
    monkeypatch.setenv("DAILY_BUDGET_USD", "1.00")
    now = datetime(2026, 11, 8, 15, 0, tzinfo=timezone.utc)
    db = _usage_db(tmp_path, [("2026-11-07T23:59:00+00:00", 5.0), ("2026-11-08T10:00:00+00:00", 0.6)])
    assert limits.spent_today(db, now) == pytest.approx(0.6)
    limits.check_budget(db, now)  # 0.60 < 1.00
    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO usage_log VALUES (?, ?)", ("2026-11-08T11:00:00+00:00", 0.5))
    conn.commit()
    conn.close()
    with pytest.raises(limits.LimitExceeded, match="daily question limit"):
        limits.check_budget(db, now)  # 0.60 + 0.50 >= 1.00


def test_data_dir_moves_the_sqlite_files(monkeypatch, tmp_path):
    import core.database as database

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    try:
        assert importlib.reload(database).DB_PATH == str(tmp_path / "usage.db")
    finally:
        monkeypatch.delenv("DATA_DIR")
        importlib.reload(database)
