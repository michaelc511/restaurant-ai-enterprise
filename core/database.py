"""F11: Relational DB & Text-to-SQL Tool - persists usage_log rows so F6's
token/cost numbers survive process restarts. Also gives future text-to-SQL
tooling a real table to query.
"""
import sqlite3
from datetime import datetime, timezone

from core.telemetry import UsageInfo

DB_PATH = "usage.db"


def init_db(db_path: str = DB_PATH):
    """F11: create usage_log if it doesn't exist yet. Safe to call on every startup."""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usage_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            cuisine TEXT NOT NULL,
            session_id TEXT NOT NULL,
            question TEXT NOT NULL,
            prompt_tokens INTEGER NOT NULL,
            completion_tokens INTEGER NOT NULL,
            total_tokens INTEGER NOT NULL,
            cost_usd REAL NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def log_call(cuisine: str, session_id: str, question: str, usage: UsageInfo, db_path: str = DB_PATH):
    """F11: write one row per LLM call - the durable counterpart to F6's in-memory session_usage_totals."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO usage_log
           (timestamp, cuisine, session_id, question, prompt_tokens, completion_tokens, total_tokens, cost_usd)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            datetime.now(timezone.utc).isoformat(),
            cuisine,
            session_id,
            question,
            usage.prompt_tokens,
            usage.completion_tokens,
            usage.total_tokens,
            usage.total_cost_usd,
        ),
    )
    conn.commit()
    conn.close()


def get_session_totals(session_id: str, db_path: str = DB_PATH) -> dict:
    """F11: durable totals via SQL SUM() - no second totals table to keep in sync."""
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        """SELECT COALESCE(SUM(prompt_tokens), 0), COALESCE(SUM(completion_tokens), 0),
                  COALESCE(SUM(total_tokens), 0), COALESCE(SUM(cost_usd), 0.0)
           FROM usage_log WHERE session_id = ?""",
        (session_id,),
    ).fetchone()
    conn.close()
    return {
        "prompt_tokens": row[0],
        "completion_tokens": row[1],
        "total_tokens": row[2],
        "total_cost_usd": row[3],
    }
