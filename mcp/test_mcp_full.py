
import sys
import os
import asyncio

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import AsyncExitStack


async def test_mcp_server():
    print("="*60)
    print("   测试完整版MCP流程 (Client <-> Server)")
    print("="*60)

    exit_stack = AsyncExitStack()

    try:
        server_script = os.path.join(os.path.dirname(__file__), "mcp_tools.py")
        print(f"\n[1/5] 正在启动MCP Server: {server_script}")

        server_params = StdioServerParameters(
            command=sys.executable,
            args=[server_script]
        )

        stdio_transport = await exit_stack.enter_async_context(stdio_client(server_params))
        stdio, write = stdio_transport
        session = await exit_stack.enter_async_context(ClientSession(stdio, write))

        print("  OK MCP Server 启动成功")

        print("\n[2/5] 正在初始化Session...")
        await session.initialize()
        print("  OK Session 初始化成功")

        print("\n[3/5] 正在获取可用工具列表...")
        response = await session.list_tools()
        tools = response.tools
        print(f"  OK 找到 {len(tools)} 个工具: {[tool.name for tool in tools]}")

        print("\n[4/5] 正在测试工具调用...")

        test_cases = [
            ("eda_analysis", {"data_name": "sales_data"}, "探索性数据分析"),
            ("feature_analysis", {"data_name": "sales_data"}, "特征分析"),
            ("forecast", {"data_name": "sales_data", "model": "arima", "periods": 7}, "时间序列预测"),
        ]

        all_passed = True
        for tool_name, tool_args, tool_desc in test_cases:
            print(f"  测试 {tool_desc}...")
            result = await session.call_tool(tool_name, tool_args)

            output_text = ""
            for content in result.content:
                if content.type == "text":
                    output_text = content.text
                    break

            if output_text:
                print(f"    OK {tool_desc} 调用成功")
                preview = output_text[:80].replace("\n", " ")
                print(f"    输出预览: {preview}...")
            else:
                print(f"    FAIL {tool_desc} 调用失败")
                all_passed = False

        print("\n[5/5] 测试完成")

        if all_passed:
            print("\n" + "="*60)
            print("   OK 完整版MCP流程验证通过！")
            print("="*60)
            print("\n验证结论：")
            print("  1. OK MCP Server 能够正常启动")
            print("  2. OK MCP Client 能够连接到 Server")
            print("  3. OK Client 能够获取工具列表")
            print("  4. OK Client 能够调用工具并获取结果")
            print("\n完整的MCP流程 (Client <-> Server) 验证成功！")
        else:
            print("\n" + "="*60)
            print("   FAIL 部分测试失败")
            print("="*60)

        return all_passed

    except Exception as e:
        print(f"\nFAIL 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await exit_stack.aclose()


if __name__ == "__main__":
    success = asyncio.run(test_mcp_server())
    sys.exit(0 if success else 1)
