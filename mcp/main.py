
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from llm_client import LLMClient
from mcp_tools import server
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import AsyncExitStack


class TimeSeriesAssistant:
    def __init__(self):
        self.llm_client = LLMClient()
        self.exit_stack = AsyncExitStack()
        self.session = None

    async def connect_mcp_server(self):
        server_script = os.path.join(os.path.dirname(__file__), "mcp_tools.py")
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[server_script]
        )

        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        await self.session.initialize()

        response = await self.session.list_tools()
        print(f"OK 已连接MCP服务器，可用工具：{[tool.name for tool in response.tools]}")

    async def process_query(self, query):
        print(f"\n用户查询：{query}")

        intent = self.llm_client.analyze_intent(query)
        tool_name = intent["tool"]
        tool_args = intent["args"]

        tool_desc = {
            "eda_analysis": "探索性数据分析",
            "preprocessing": "数据预处理",
            "feature_analysis": "特征分析",
            "forecast": "时间序列预测"
        }

        print(f"→ 识别意图：{tool_desc.get(tool_name, tool_name)}")
        print(f"→ 调用工具：{tool_name}，参数：{tool_args}")

        result = await self.session.call_tool(tool_name, tool_args)

        output = []
        for content in result.content:
            if content.type == "text":
                output.append(content.text)

        return "\n".join(output)

    async def run(self):
        await self.connect_mcp_server()

        print("\n" + "="*60)
        print("   鸿溯 - 时间序列数据分析助手 (Demo)")
        print("="*60)
        print("示例查询：")
        print("  1. 帮我看看这个数据的基本情况")
        print("  2. 分析一下数据的特征和相关性")
        print("  3. 帮我预测未来7天的趋势")
        print("  4. 退出 (输入 'quit' 或 'exit')")
        print("="*60 + "\n")

        while True:
            try:
                query = input("请输入您的分析需求：").strip()

                if query.lower() in ["quit", "exit", "退出"]:
                    print("感谢使用，再见！")
                    break

                if not query:
                    continue

                result = await self.process_query(query)
                print("\n" + "-"*60)
                print("分析结果：")
                print("-"*60)
                print(result)
                print("-"*60 + "\n")

            except KeyboardInterrupt:
                print("\n\n感谢使用，再见！")
                break
            except Exception as e:
                print(f"\n发生错误：{e}")

    async def close(self):
        await self.exit_stack.aclose()


async def main():
    assistant = TimeSeriesAssistant()
    try:
        await assistant.run()
    finally:
        await assistant.close()


if __name__ == "__main__":
    asyncio.run(main())
