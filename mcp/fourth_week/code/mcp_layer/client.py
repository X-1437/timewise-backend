import sys
from contextlib import AsyncExitStack
from pathlib import Path

from fastapi import FastAPI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPClient:
    def __init__(self):
        self._exit_stack = AsyncExitStack()
        self._session: ClientSession | None = None

    async def connect(self) -> None:
        server_script = Path(__file__).parent / "tools" / "mcp_tools.py"
        server_params = StdioServerParameters(command=sys.executable, args=[str(server_script)])

        stdio_transport = await self._exit_stack.enter_async_context(stdio_client(server_params))
        stdio, write = stdio_transport
        self._session = await self._exit_stack.enter_async_context(ClientSession(stdio, write))
        await self._session.initialize()

    async def close(self) -> None:
        await self._exit_stack.aclose()

    async def list_tools(self) -> list[str]:
        if self._session is None:
            raise RuntimeError("MCP未连接")
        resp = await self._session.list_tools()
        return [t.name for t in resp.tools]

    async def call_tool(self, tool_name: str, tool_args: dict) -> str:
        if self._session is None:
            raise RuntimeError("MCP未连接")
        result = await self._session.call_tool(tool_name, tool_args)
        output = []
        for content in result.content:
            if content.type == "text":
                output.append(content.text)
        return "\n".join(output)


async def init_mcp(app: FastAPI) -> None:
    client = MCPClient()
    await client.connect()
    app.state.mcp_client = client


async def close_mcp(app: FastAPI) -> None:
    client: MCPClient | None = getattr(app.state, "mcp_client", None)
    if client is not None:
        await client.close()
