"""F8: Reads live restaurant-ops data (daily specials, hours & events) plus the
company org directory and items list (org, items tabs) from the 'org' Google
Sheet via a service account. Shared by api/mcp_server.py (exposed
as MCP tools for agents) and menu_api.py (called directly as plain functions) -
one implementation, two consumers, same pattern F6/F10 already use.
"""
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import gspread
from gspread.exceptions import APIError, SpreadsheetNotFound, WorksheetNotFound

SPREADSHEET_NAME = "org"
SERVICE_ACCOUNT_PATH = Path(__file__).resolve().parent.parent / "secrets" / "service_account.json"

DAILY_SPECIALS_TAB = "specials"  # the actual tab name in the live sheet (not "Daily Specials")
HOURS_AND_EVENTS_TAB = "dates"  # the actual tab name in the live sheet (not "Hours & Events")
ORG_TAB = "org"  # F8: company directory - offices, departments, vendors, etc. with a contact each
ITEMS_TAB = "items"  # F8: non-date facts per App/Tenant - announcements, statuses, prices, promotions

SPECIALS_KEYWORDS = ("special",)
HOURS_KEYWORDS = ("hour", "open", "close", "holiday")
# F8: substring-matched against both the question and each items row's Category, so "any outages?"
# finds "Known Outage" rows without needing the exact category name
ITEMS_KEYWORDS = (
    "announcement", "status", "outage", "release note", "promotion", "deductible", "out-of-pocket",
    "contract", "amenit", "room type", "list price", "policy update",
)
# F8: whole-word match - "who"/"head" as substrings would hit "whole"/"ahead"
ORG_PATTERN = re.compile(r"\b(who|whom|whose|heads?|contact|email|phone|office|offices|department|manager|director)\b")

WEEKDAY_NAMES = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")

_client_cache: Optional[gspread.Client] = None


# F8 FastMCP Server Endpoint
def resolve_target_days(question: str) -> list[date]:
    """Heuristic relative-date parser: figures out which calendar day(s) a question
    is actually asking about (tomorrow, in 3 days, a weekday name, this weekend),
    defaulting to just today when nothing matches.

    Not a full NLP date parser - covers the common phrasings this project's demo
    questions use. "Weekend" returns both Saturday and Sunday since specials/hours
    can differ per day; everything else resolves to a single date.

    Returns:
        A list of one or more datetime.date objects, always at least [today].
    """
    q = question.strip().lower()
    today = date.today()

    if "day after tomorrow" in q:
        return [today + timedelta(days=2)]
    if "tomorrow" in q:
        return [today + timedelta(days=1)]

    m = re.search(r"in\s+(\d+)\s*days?", q) or re.search(r"(\d+)\s*days?\s*(?:from now|from today|out|later)", q)
    if m:
        return [today + timedelta(days=int(m.group(1)))]

    if "weekend" in q:
        days_until_saturday = (5 - today.weekday()) % 7  # Monday=0 ... Saturday=5
        saturday = today + timedelta(days=days_until_saturday)
        return [saturday, saturday + timedelta(days=1)]

    for i, weekday_name in enumerate(WEEKDAY_NAMES):
        if re.search(rf"\b{weekday_name}\b", q) or re.search(rf"\b{weekday_name[:3]}\b", q):
            days_ahead = (i - today.weekday()) % 7  # 0 if it's already that weekday today
            return [today + timedelta(days=days_ahead)]

    return [today]


# F8 FastMCP Server Endpoint
def detect_ops_intent(question: str) -> Optional[str]:
    """Heuristic keyword router: guesses whether a natural-language question is
    really asking about live ops data (specials/hours) rather than PDF menu
    content, so it can be routed to this module instead of the RAG chain.

    Not real intent understanding - a simple substring match, good enough to
    catch obvious phrasing like "what are today's specials?" or "are you open on
    Sunday?". Query Guardrails & Intent Gating (F19)'s classify_intent() (core/guardrails.py)
    now runs before this, in menu_api.py/engine_api.py's ask(), and rejects off-topic
    questions outright - but it doesn't replace this heuristic's specials-vs-hours-vs-menu
    routing, so both still run.

    Order matters: items keywords are more specific than org's "who"/"contact", and org runs before
    hours so "office hours" reads the org tab's per-office hours, not the restaurant's dates tab.

    Returns:
        "specials", "items", "org", "hours", or None (fall through to the RAG chain as normal).
    """
    q = question.strip().lower()
    if any(kw in q for kw in SPECIALS_KEYWORDS):
        return "specials"
    if any(kw in q for kw in ITEMS_KEYWORDS):
        return "items"
    if ORG_PATTERN.search(q):
        return "org"
    if any(kw in q for kw in HOURS_KEYWORDS):
        return "hours"
    return None


# F8 FastMCP Server Endpoint
def _get_client() -> gspread.Client:
    """Authenticate once and reuse the client - same 'cache once, reuse after' pattern
    build_qa_chain() already uses for FAISS vectorstores. Stateless in the MCP sense:
    only the auth session is cached, never sheet data, so every call re-fetches live rows.
    """
    global _client_cache
    if _client_cache is None:
        _client_cache = gspread.service_account(filename=str(SERVICE_ACCOUNT_PATH))
    return _client_cache


# F8 FastMCP Server Endpoint
def _open_tab(tab_name: str):
    try:
        return _get_client().open(SPREADSHEET_NAME).worksheet(tab_name)
    except SpreadsheetNotFound:
        raise RuntimeError(
            f"Spreadsheet '{SPREADSHEET_NAME}' not found, or not shared with the service account's client_email."
        )
    except WorksheetNotFound:
        raise RuntimeError(f"Tab '{tab_name}' not found in the '{SPREADSHEET_NAME}' spreadsheet - check for a rename.")
    except APIError as e:
        raise RuntimeError(f"Google Sheets API error (network issue or rate limit): {e}")


def _is_active(value: str) -> bool:
    return str(value).strip().lower() in ("true", "yes", "y", "1", "active")


# F8 FastMCP Server Endpoint
def get_daily_specials(day: Optional[str] = None) -> list[dict]:
    """Look up today's (or a given weekday's) active daily specials.

    Args:
        day: A weekday like "Mon", "Fri", or "All Week". If omitted, returns every
            active special regardless of day.

    Returns:
        A list of dicts, one per active special, with keys matching the sheet's
        columns: Day, Dish Name, Category, Description, Price, Allergens.

    Raises:
        RuntimeError: if the sheet/tab can't be reached (missing, renamed, a
            network issue, or a Google Sheets API rate limit).
    """
    rows = _open_tab(DAILY_SPECIALS_TAB).get_all_records()
    specials = [row for row in rows if _is_active(row.get("Is Active", ""))]
    if day and day.strip().lower() != "all week":
        wanted = day.strip().lower()
        specials = [
            row for row in specials
            if str(row.get("Day", "")).strip().lower() in (wanted, "all week")
        ]
    return specials


# F8 FastMCP Server Endpoint
def get_hours_and_events(target_date: Optional[str] = None) -> list[dict]:
    """Look up hours, holiday schedules, or closure notices.

    Args:
        target_date: A specific date matching the sheet's Date column format
            (e.g. "2026-08-27"). If omitted, returns every row in the tab.

    Returns:
        A list of dicts, one per matching row, with keys matching the sheet's
        columns: Date, Day, Event / Holiday, Status, Open Time, Close Time,
        Staff Notes.

    Raises:
        RuntimeError: if the sheet/tab can't be reached (missing, renamed, a
            network issue, or a Google Sheets API rate limit).
    """
    rows = _open_tab(HOURS_AND_EVENTS_TAB).get_all_records()
    if target_date:
        wanted = target_date.strip()
        rows = [row for row in rows if str(row.get("Date", "")).strip() == wanted]
    return rows


def _same(a: str, b: str) -> bool:  # F8: case/whitespace-insensitive cell match
    return str(a).strip().lower() == str(b).strip().lower()


def _mentions(question: str, phrase: str) -> bool:  # F8: whole-word, so "Product A" doesn't match "a"
    phrase = str(phrase).strip().lower()
    return bool(phrase) and re.search(rf"\b{re.escape(phrase)}\b", question.lower()) is not None


# F8 FastMCP Server Endpoint
def get_org(org_type: Optional[str] = None, name: Optional[str] = None) -> list[dict]:
    """Look up active rows in the company org directory.

    Args:
        org_type: A Type like "Department", "Office", or "Vendor". Omit for every type.
        name: A Name like "Legal" or "London". Omit for every name.

    Returns:
        A list of dicts with keys matching the sheet's columns: Type, Name, Parent,
        Location, Contact, Email, Notes, Is Active.

    Raises:
        RuntimeError: if the sheet/tab can't be reached.
    """
    rows = [row for row in _open_tab(ORG_TAB).get_all_records() if _is_active(row.get("Is Active", ""))]
    if org_type:
        rows = [row for row in rows if _same(row.get("Type", ""), org_type)]
    if name:
        rows = [row for row in rows if _same(row.get("Name", ""), name)]
    return rows


# F8 FastMCP Server Endpoint
def get_items(category: Optional[str] = None, tenant: Optional[str] = None) -> list[dict]:
    """Look up active rows in the items list (announcements, statuses, prices, promotions).

    Args:
        category: A Category like "System Status" or "Announcement". Omit for every category.
        tenant: A Tenant like "London" or "Gold". Omit for every tenant.

    Returns:
        A list of dicts with keys matching the sheet's columns: App, Tenant, Category,
        Name, Description, Value, Applies To, Is Active.

    Raises:
        RuntimeError: if the sheet/tab can't be reached.
    """
    rows = [row for row in _open_tab(ITEMS_TAB).get_all_records() if _is_active(row.get("Is Active", ""))]
    if category:
        rows = [row for row in rows if _same(row.get("Category", ""), category)]
    if tenant:
        rows = [row for row in rows if _same(row.get("Tenant", ""), tenant)]
    return rows


# F8 FastMCP Server Endpoint
def find_org_rows(question: str) -> list[dict]:
    """Org rows a free-text question is about: rows whose Name it mentions ("Who heads Legal?"),
    else every row of a Type it mentions ("What are the office hours?" -> all Offices).
    [] means nothing matched, so the caller falls through to the RAG engine.
    """
    rows = get_org()
    by_name = [row for row in rows if _mentions(question, row.get("Name", ""))]
    if by_name:
        return by_name
    return [
        row for row in rows
        if _mentions(question, row.get("Type", "")) or _mentions(question, f"{row.get('Type', '')}s")
    ]


# F8 FastMCP Server Endpoint
def find_item_rows(question: str) -> list[dict]:
    """Items rows a free-text question is about: rows whose Category the question names (exactly, or
    via a shared ITEMS_KEYWORDS stem), narrowed to any Tenant it also names.
    [] means nothing matched, so the caller falls through to the RAG engine.
    """
    q = question.lower()
    keywords = [kw for kw in ITEMS_KEYWORDS if kw in q]
    rows = [
        row for row in get_items()
        if str(row.get("Category", "")).strip().lower() in q
        or any(kw in str(row.get("Category", "")).lower() for kw in keywords)
    ]
    for_tenant = [row for row in rows if _mentions(question, row.get("Tenant", ""))]
    return for_tenant or rows
