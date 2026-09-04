"""F8: FastMCP server - exposes live restaurant-ops data (daily specials, hours &
events) from the 'sushi' Google Sheet as MCP tools for agent runtimes. Read logic
lives in core/sheets.py; menu_api.py calls those same functions directly for the
FastAPI-facing /specials and /hours endpoints - one implementation, two consumers,
same pattern F6/F10 already use. Stateless: every tool call re-authenticates
against the same cached client and re-reads the sheet fresh, no data cached
between calls and no per-session state kept across invocations.

Run standalone (stdio transport, for MCP clients like Claude Desktop):
    python3 api/mcp_server.py
"""
import sys
from pathlib import Path
from typing import Optional

# Running this file directly (python3 api/mcp_server.py - how an MCP client like
# Claude Desktop launches it) only puts api/ on sys.path, not menu-4ap/, so
# "core" wouldn't otherwise be importable. Add the project root explicitly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastmcp import FastMCP

from core.sheets import get_daily_specials, get_hours_and_events

mcp = FastMCP("restaurant-ops-mcp")


# F8 FastMCP Server Endpoint
@mcp.tool
def daily_specials(day: Optional[str] = None) -> list[dict]:
    """Look up today's (or a given weekday's) active daily specials for the sushi menu.

    Args:
        day: A weekday like "Mon", "Fri", or "All Week". Omit to get every active
            special regardless of day.

    Returns:
        A list of specials, each with Day, Dish Name, Category, Description,
        Price, and Allergens.
    """
    return get_daily_specials(day)


# F8 FastMCP Server Endpoint
@mcp.tool
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


if __name__ == "__main__":
    mcp.run(transport="stdio")
