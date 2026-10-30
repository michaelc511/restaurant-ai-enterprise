"""F23-style unit tests for F8's MCP client - core/mcp_client.py - talking to the real
api/mcp_server.py over MCP's in-memory transport, with only the sheet reads underneath it mocked,
so tests run with no network and no service account.
"""
import asyncio

import pytest

import api.mcp_server as mcp_server
from core.mcp_client import call_mcp_tool, call_mcp_tools, list_mcp_tools
from core.sanitize import CONTEXT_START


def test_call_mcp_tool_returns_rows_as_dicts(monkeypatch):
    monkeypatch.setattr(mcp_server, "get_daily_specials", lambda day: [{"Dish Name": "Test Special", "Day": day}])

    rows = call_mcp_tool("daily_specials", {"day": "Fri"})

    assert rows == [{"Dish Name": "Test Special", "Day": "Fri"}]


def test_call_mcp_tool_drops_none_args(monkeypatch):
    seen = {}

    def fake_get_org(type=None, name=None):
        seen.update(type=type, name=name)
        return []
    monkeypatch.setattr(mcp_server, "get_org", fake_get_org)

    call_mcp_tool("org_directory", {"type": None, "name": "Legal"})

    assert seen == {"type": None, "name": "Legal"}


def test_call_mcp_tool_raises_runtime_error_on_tool_failure(monkeypatch):
    def broken(day=None):
        raise RuntimeError("sheet down")
    monkeypatch.setattr(mcp_server, "get_daily_specials", broken)

    with pytest.raises(RuntimeError, match="sheet down"):  # F8: same contract core.sheets has
        call_mcp_tool("daily_specials")


def test_list_mcp_tools_returns_function_schemas():
    tools = asyncio.run(list_mcp_tools())

    names = {t["function"]["name"] for t in tools}
    assert names == {"daily_specials", "hours_and_events", "org_directory", "company_items"}
    assert all(t["type"] == "function" for t in tools)


def test_call_mcp_tools_sanitizes_results_and_reports_errors(monkeypatch):
    monkeypatch.setattr(mcp_server, "get_items", lambda category=None, tenant=None: [{"Name": "Status OK"}])

    def broken(target_date=None):
        raise RuntimeError("sheet down")
    monkeypatch.setattr(mcp_server, "get_hours_and_events", broken)

    ok, failed = asyncio.run(call_mcp_tools([
        {"name": "company_items", "args": {}},
        {"name": "hours_and_events", "args": {}},
    ]))

    assert ok.startswith(CONTEXT_START) and "Status OK" in ok  # F22
    assert "unavailable (" in failed and "sheet down" in failed
