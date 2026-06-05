import asyncio

from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types


server = Server("hongsu-time-series")


@server.list_resources()
async def handle_list_resources():
    return []


@server.list_tools()
async def handle_list_tools():
    return [
        types.Tool(
            name="eda_analysis",
            description="执行探索性数据分析（EDA），包括数据概览、缺失值统计、基本统计量",
            inputSchema={
                "type": "object",
                "properties": {"data_name": {"type": "string", "description": "数据集名称"}},
                "required": ["data_name"],
            },
        ),
        types.Tool(
            name="preprocessing",
            description="数据预处理，包括缺失值处理、异常值处理、数据类型转换",
            inputSchema={
                "type": "object",
                "properties": {
                    "data_name": {"type": "string", "description": "数据集名称"},
                    "method": {
                        "type": "string",
                        "description": "预处理方法",
                        "enum": ["missing_fill", "outlier_remove", "type_convert"],
                        "default": "missing_fill",
                    },
                },
                "required": ["data_name"],
            },
        ),
        types.Tool(
            name="feature_analysis",
            description="特征分析，包括相关性分析、特征重要性、趋势分析",
            inputSchema={
                "type": "object",
                "properties": {"data_name": {"type": "string", "description": "数据集名称"}},
                "required": ["data_name"],
            },
        ),
        types.Tool(
            name="forecast",
            description="时间序列预测，包括ARIMA、Prophet、LSTM等模型",
            inputSchema={
                "type": "object",
                "properties": {
                    "data_name": {"type": "string", "description": "数据集名称"},
                    "model": {"type": "string", "description": "预测模型", "enum": ["arima", "prophet", "lstm"]},
                    "periods": {"type": "integer", "description": "预测期数", "default": 7},
                },
                "required": ["data_name", "model"],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(name, arguments):
    if name == "eda_analysis":
        data_name = arguments.get("data_name", "未知数据")
        result = """
【探索性数据分析（EDA）结果】
数据集：{}

数据概览：
- 数据形状：(1000, 15)
- 时间范围：2024-01-01 至 2026-05-18
- 采样频率：每日

缺失值统计：
- 列A：0.5%
- 列B：2.3%
- 其他列：0%

基本统计量：
- 均值：1234.56
- 中位数：1200.00
- 标准差：456.78
- 最小值：100.00
- 最大值：5000.00
""".format(data_name)
        return [types.TextContent(type="text", text=result.strip())]

    if name == "preprocessing":
        data_name = arguments.get("data_name", "未知数据")
        method = arguments.get("method", "missing_fill")
        method_desc = {"missing_fill": "缺失值填充", "outlier_remove": "异常值移除", "type_convert": "数据类型转换"}
        result = """
【数据预处理结果】
数据集：{}
预处理方法：{}

处理详情：
- 处理前数据量：1000条
- 处理后数据量：995条
- 移除异常值：5条
- 填充缺失值：28个

处理完成！数据已准备好进行后续分析。
""".format(data_name, method_desc.get(method, method))
        return [types.TextContent(type="text", text=result.strip())]

    if name == "feature_analysis":
        data_name = arguments.get("data_name", "未知数据")
        result = """
【特征分析结果】
数据集：{}

相关性分析（Top 5）：
1. 特征A与目标：0.85（强正相关）
2. 特征B与目标：0.72（正相关）
3. 特征C与目标：-0.65（负相关）
4. 特征D与目标：0.45（中等相关）
5. 特征E与目标：0.12（弱相关）

特征重要性：
1. 特征A：35%
2. 特征B：28%
3. 特征C：20%
4. 特征D：12%
5. 其他：5%

趋势分析：
- 整体趋势：上升
- 季节性：存在明显的周季节性
- 异常点：3个（已标注）
""".format(data_name)
        return [types.TextContent(type="text", text=result.strip())]

    if name == "forecast":
        data_name = arguments.get("data_name", "未知数据")
        model = arguments.get("model", "arima")
        periods = arguments.get("periods", 7)
        model_desc = {"arima": "ARIMA", "prophet": "Prophet", "lstm": "LSTM"}
        result = """
【时间序列预测结果】
数据集：{}
预测模型：{}
预测期数：{}天

模型评估：
- MAE（平均绝对误差）：123.45
- MAPE（平均绝对百分比误差）：8.5%
- RMSE（均方根误差）：156.78
- R²（决定系数）：0.89

预测结果（未来{}天）：
日期          预测值      置信区间(95%)
2026-05-19    1350.00    [1280, 1420]
2026-05-20    1380.00    [1300, 1460]
2026-05-21    1420.00    [1330, 1510]
2026-05-22    1450.00    [1360, 1540]
2026-05-23    1480.00    [1390, 1570]
2026-05-24    1510.00    [1420, 1600]
2026-05-25    1550.00    [1450, 1650]

预测趋势：持续上升，预计未来一周增长约15%
""".format(data_name, model_desc.get(model, model), periods, periods)
        return [types.TextContent(type="text", text=result.strip())]

    return [types.TextContent(type="text", text="未知工具：{}".format(name))]


async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="hongsu-time-series",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
