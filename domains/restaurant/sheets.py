# F8/F12: Restaurant-only live-data readers - the 'specials' and 'dates' tabs of the 'org' Google
# Sheet. The shared client, tab opening and the company-wide org/items tabs stay in core/sheets.py.
from typing import Optional

from core import sheets  # F8: module reference, not names, so tests can monkeypatch sheets._open_tab

DAILY_SPECIALS_TAB = "specials"  # the actual tab name in the live sheet (not "Daily Specials")
HOURS_AND_EVENTS_TAB = "dates"  # the actual tab name in the live sheet (not "Hours & Events")


# F8 FastMCP Server Endpoint
def get_daily_specials(day: Optional[str] = None) -> list[dict]:
    """Look up today's (or a given weekday's) active daily specials.

    Args:
        day: A weekday like "Mon", "Fri", or "All Week". If omitted, returns every
            active special regardless of day. Sheet rows may use ranges like
            "Tues - Fri", which match every day in the range.

    Returns:
        A list of dicts, one per active special, with keys matching the sheet's
        columns: Day, Hours, Dish Name, Category, Description, Price, Allergens.

    Raises:
        RuntimeError: if the sheet/tab can't be reached (missing, renamed, a
            network issue, or a Google Sheets API rate limit).
    """
    rows = sheets._open_tab(DAILY_SPECIALS_TAB).get_all_records()
    specials = [row for row in rows if sheets._is_active(row.get("Is Active", ""))]
    if day and day.strip().lower() != "all week":
        specials = [row for row in specials if _day_matches(str(row.get("Day", "")), day)]
    return specials


_WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def _day_matches(cell: str, day: str) -> bool:  # F8: a sheet Day cell is "All Week", a weekday, or a range like "Tues - Fri"
    cell = cell.strip().lower()
    wanted = day.strip().lower()[:3]
    if cell == "all week":
        return True
    if "-" not in cell:
        return cell[:3] == wanted  # F8: "Tue" / "Tues" / "Tuesday" all match "Tue"
    start, _, end = (part.strip()[:3] for part in cell.partition("-"))
    if start not in _WEEKDAYS or end not in _WEEKDAYS or wanted not in _WEEKDAYS:
        return False
    i, j, k = _WEEKDAYS.index(start), _WEEKDAYS.index(end), _WEEKDAYS.index(wanted)
    return i <= k <= j if i <= j else k >= i or k <= j  # F8: wraps, e.g. "Fri - Mon"


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
    rows = sheets._open_tab(HOURS_AND_EVENTS_TAB).get_all_records()
    if target_date:
        wanted = target_date.strip()
        rows = [row for row in rows if str(row.get("Date", "")).strip() == wanted]
    return rows
