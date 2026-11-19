# F8/F12: Restaurant MCP tools - registered on api/mcp_server.py's server by register(); the
# company-wide org_directory/company_items tools stay in the server itself.
from typing import Optional

from domains.restaurant.sheets import get_daily_specials, get_hours_and_events


# F8 FastMCP Server Endpoint
def daily_specials(day: Optional[str] = None) -> list[dict]:
    """Look up today's (or a given weekday's) active daily specials and happy hour items
    for the sushi menu. Happy hour rows have Category "Happy Hour".

    Args:
        day: A weekday like "Mon", "Fri", or "All Week". Omit to get every active
            special regardless of day (use this for "when is happy hour?").

    Returns:
        A list of specials, each with Day, Hours, Dish Name, Category, Description,
        Price, and Allergens.
    """
    return get_daily_specials(day)


# F8 FastMCP Server Endpoint
def hours_and_events(target_date: Optional[str] = None) -> list[dict]:
    """Look up restaurant hours, holiday schedules, or closure notices.

    Args:
        target_date: A specific date, e.g. "2026-08-27". Omit to get the full
            hours & events schedule.

    Returns:
        A list of rows, each with Date, Day, Event / Holiday, Status, Open Time,
        Close Time, and Staff Notes.
    """
    return get_hours_and_events(target_date)


def register(mcp) -> None:  # F12: api/mcp_server.py calls this for the active domain
    mcp.tool(daily_specials)
    mcp.tool(hours_and_events)
