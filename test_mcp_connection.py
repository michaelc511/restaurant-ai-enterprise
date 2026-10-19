"""F8: Standalone verification for api/mcp_server.py - spawns the real server as a
subprocess over stdio (the same way an MCP client like Claude Desktop would) and
exercises all four tools against the live 'sushi' Google Sheet.

Run:
    cd menu-4ap
    source venv/bin/activate
    python3 test_mcp_connection.py
"""
import asyncio

from fastmcp import Client


async def main():
    async with Client("api/mcp_server.py") as client:
        tools = await client.list_tools()
        print(f"Discovered {len(tools)} tool(s):")
        for tool in tools:
            print(f"  - {tool.name}: {tool.description.splitlines()[0]}")

        print("\ndaily_specials() - all active specials:")
        result = await client.call_tool("daily_specials", {})
        print(result.data)

        print("\ndaily_specials(day='Fri') - Friday only:")
        result = await client.call_tool("daily_specials", {"day": "Fri"})
        print(result.data)

        print("\nhours_and_events() - full schedule:")
        result = await client.call_tool("hours_and_events", {})
        print(result.data)

        print("\norg_directory(name='Legal') - who heads Legal:")
        result = await client.call_tool("org_directory", {"name": "Legal"})
        print(result.data)

        print("\norg_directory(type='Office') - office hours:")
        result = await client.call_tool("org_directory", {"type": "Office"})
        print(result.data)

        print("\ncompany_items(category='System Status') - IT system status:")
        result = await client.call_tool("company_items", {"category": "System Status"})
        print(result.data)


if __name__ == "__main__":
    asyncio.run(main())
