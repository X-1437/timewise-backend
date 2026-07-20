import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp_layer.client import MCPClient


async def main() -> None:
    client = MCPClient()
    await asyncio.wait_for(client.connect(), timeout=10)
    tools = await asyncio.wait_for(client.list_tools(), timeout=10)
    print("MCP_OK", len(tools))
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
