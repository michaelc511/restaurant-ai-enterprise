"""F8: FastMCP server - exposes live restaurant-ops data (daily specials, hours &
events) and the company org directory and items list from the 'org' Google Sheet
as MCP tools for agent runtimes. Read logic
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

from core.sheets import get_daily_specials, get_hours_and_events, get_org, get_items

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


# F8 FastMCP Server Endpoint
@mcp.tool
def org_directory(type: Optional[str] = None, name: Optional[str] = None) -> list[dict]:
    """Look up the company org directory: who heads a department, office hours and
    contacts, vendors, and so on.

    Args:
        type: A Type like "Department", "Office", "Vendor", or "Clinic". Omit for every type.
        name: A Name like "Legal" or "London". Omit for every name.

    Returns:
        A list of rows, each with Type, Name, Parent, Location, Contact, Email,
        and Notes.
    """
    return get_org(type, name)


# F8 FastMCP Server Endpoint
@mcp.tool
def company_items(category: Optional[str] = None, tenant: Optional[str] = None) -> list[dict]:
    """Look up company items: announcements, system status, known outages, promotions,
    prices, and other non-date facts.

    Args:
        category: A Category like "System Status" or "Announcement". Omit for every category.
        tenant: A Tenant like "London" or "Gold". Omit for every tenant.

    Returns:
        A list of rows, each with App, Tenant, Category, Name, Description, Value,
        and Applies To.
    """
    return get_items(category, tenant)


if __name__ == "__main__":
    mcp.run(transport="stdio")
