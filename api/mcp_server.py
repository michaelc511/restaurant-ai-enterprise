"""F8: FastMCP server - exposes the company org directory and items list from the 'org'
Google Sheet as MCP tools for agent runtimes, plus the active domain pack's own tools
(F12: domains/<DOMAIN>/tools.py - for restaurant, daily specials and hours & events).
Read logic lives in core/sheets.py and domains/<DOMAIN>/sheets.py; menu_api.py calls
those same functions directly for its /specials and /hours endpoints. Stateless: every tool call re-authenticates
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

import importlib

from fastmcp import FastMCP

from core.domain import DOMAIN, domain  # F12
from core.sheets import get_org, get_items

mcp = FastMCP(domain.MCP_SERVER_NAME)  # F12: e.g. "restaurant-ops-mcp"

try:  # F12: a domain pack may have no live-data tools of its own
    importlib.import_module(f"domains.{DOMAIN}.tools").register(mcp)
except ModuleNotFoundError as e:
    if e.name != f"domains.{DOMAIN}.tools":
        raise


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
