# F8: MCP client - the one way engine_api.py and its engines read live sheet data, over the Model
# Context Protocol from api/mcp_server.py instead of importing core.sheets directly. plain_rag and
# langgraph get it through engine_api.py's F8 routing; the orchestrator (F13)'s MCP Tools agent uses
# the discovery/batch helpers to let the LLM pick tools. menu_api.py keeps its direct core.sheets calls.
import asyncio
import os
from typing import Any, Optional

from core.sanitize import sanitize_content  # F22

MCP_SERVER = os.environ.get("MCP_SERVER", "")  # F8: "" = in-process api/mcp_server.py; or a script path / http URL


def _mcp_target():
    """F8: MCP_SERVER if set (a script path like "api/mcp_server.py" for stdio, or an http URL), else
    the server object in-process - still the full MCP protocol, without spawning a subprocess per call."""
    if MCP_SERVER:
        return MCP_SERVER
    from api.mcp_server import mcp  # lazy import - only needed for the in-process default
    return mcp


async def list_mcp_tools() -> list[dict]:
    """F13: discover the server's tools at runtime, as OpenAI-style function schemas for bind_tools() -
    a tool added to api/mcp_server.py shows up here with no engine change."""
    from fastmcp import Client  # lazy import - avoids a hard dependency at module load
    async with Client(_mcp_target()) as client:
        tools = await client.list_tools()
    return [
        {"type": "function", "function": {"name": t.name, "description": t.description or "", "parameters": t.input_schema}}
        for t in tools
    ]


async def call_mcp_tools(calls: list[dict]) -> list[str]:
    """F13: run an LLM's chosen tool calls over one MCP session, sanitizing each result (F22) - errors
    come back as "unavailable (...)" text so the LLM can say so rather than the request failing."""
    from fastmcp import Client  # lazy import - avoids a hard dependency at module load
    results = []
    async with Client(_mcp_target()) as client:
        for call in calls:
            result = await client.call_tool(call["name"], call["args"], raise_on_error=False)
            text = "\n".join(getattr(block, "text", "") for block in result.content)
            if result.is_error:  # F8: e.g. core.sheets' RuntimeError when the sheet is unreachable
                text = f"unavailable ({text})"
            results.append(sanitize_content(f"{call['name']}({call['args']}) -> {text}"))  # F22: sheet cells are untrusted too
    return results


async def _call_mcp_tool(name: str, args: dict) -> Any:
    from fastmcp import Client  # lazy import - avoids a hard dependency at module load
    async with Client(_mcp_target()) as client:
        result = await client.call_tool(name, args, raise_on_error=False)
    if result.is_error:
        raise RuntimeError("\n".join(getattr(block, "text", "") for block in result.content))
    return result.data


def call_mcp_tool(name: str, args: Optional[dict] = None) -> list[dict]:
    """F8: synchronous single tool call for engine_api.py's deterministic routing. Raises RuntimeError
    on a tool error, the same contract core.sheets has, so callers' existing except clauses still apply.
    Uses asyncio.run, so call it from sync code (FastAPI runs sync endpoints in a worker thread)."""
    args = {k: v for k, v in (args or {}).items() if v is not None}
    return asyncio.run(_call_mcp_tool(name, args))
