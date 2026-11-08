# F21: usage limits for a public deploy without login (the rate-limiting half of F21; API-key auth is
# still not built). Caps OpenAI spend per UTC day from F11's usage_log and limits /ask per visitor IP.
# Each limit is an env var; 0 switches it off. Counters live in memory - right for a single machine.
import os
import sqlite3
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Optional

DEFAULT_PER_MINUTE = 5
DEFAULT_PER_DAY = 50
DEFAULT_DAILY_BUDGET_USD = 1.00

_lock = threading.Lock()
_calls: dict[str, deque] = defaultdict(deque)


class LimitExceeded(Exception):  # F21: engine_api.py turns this into HTTP 429
    pass


def _number(name: str, default: float) -> float:
    try:
        return max(0.0, float(os.environ.get(name, default)))
    except ValueError:
        return default


def reset() -> None:  # F21: tests start from empty counters
    with _lock:
        _calls.clear()


def check_rate(client_ip: str, now: Optional[float] = None) -> None:
    per_minute = int(_number("RATE_LIMIT_PER_MINUTE", DEFAULT_PER_MINUTE))
    per_day = int(_number("RATE_LIMIT_PER_DAY", DEFAULT_PER_DAY))
    if not per_minute and not per_day:
        return
    now = time.time() if now is None else now
    with _lock:
        calls = _calls[client_ip]
        while calls and calls[0] <= now - 86400:  # F21: keep one day of history per IP
            calls.popleft()
        if per_day and len(calls) >= per_day:
            raise LimitExceeded(f"Daily limit of {per_day} questions reached for this device. Try again tomorrow.")
        if per_minute and sum(1 for t in calls if t > now - 60) >= per_minute:
            raise LimitExceeded(f"Too many questions: the limit is {per_minute} a minute. Try again shortly.")
        calls.append(now)


def spent_today(db_path: str, now: Optional[datetime] = None) -> float:
    # F21/F11: usage_log timestamps are UTC ISO strings, so a string compare against today's date works
    day = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%d")
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT COALESCE(SUM(cost_usd), 0) FROM usage_log WHERE timestamp >= ?", (day,)).fetchone()
    finally:
        conn.close()
    return float(row[0])


def check_budget(db_path: str, now: Optional[datetime] = None) -> None:
    budget = _number("DAILY_BUDGET_USD", DEFAULT_DAILY_BUDGET_USD)
    if budget and spent_today(db_path, now) >= budget:
        raise LimitExceeded("The demo's daily question limit has been reached. Please try again tomorrow.")
