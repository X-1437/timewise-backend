# 功能手册 02｜EDA（eda_analysis）

## 1. 目标与用户价值

EDA 用于回答“数据到底长什么样、质量如何、能不能继续分析”：

- 数据量/列数/时间范围
- 缺失值与重复值
- 数值列的基本统计
- 自动选择一个“目标列”做基础异常值统计（zscore 3σ）

## 2. 复用 web 端后端的点（timewise-backend）

第四周的 EDA 指标体系直接复用了 web 端 EDA 的核心计算思路：

- 缺失值统计、缺失率
- 重复值统计
- 数值列统计量（mean/median/std/min/max）
- 基于目标列的 zscore 异常值计数
- 时间范围统计

对应 web 端实现见：[eda.py](file:///d:/trae_workspace/github/timewise-backend/app/routers/eda.py#L58-L122)

本周的主要改造点是“数据来源”：

- web 端：从上传文件路径读取 DataFrame（csv/excel）
- 第四周：从 MongoDB 时序集合 `time_series_data` 按 `file_id` 拉取数据，再转 DataFrame

## 3. 第四周实现位置（你应该看哪里）

- 数据加载（MongoDB -> DataFrame）：[data.py](file:///d:/trae_workspace/data/file/fourth_week/code/analysis/data.py#L10-L28)
- EDA 计算与 Markdown 输出：[eda.py](file:///d:/trae_workspace/data/file/fourth_week/code/analysis/eda.py)
- MCP 工具封装与调用入口：[mcp_tools.py](file:///d:/trae_workspace/data/file/fourth_week/code/mcp_layer/tools/mcp_tools.py#L118-L127)

## 4. 接口定义（MCP 工具）

- Tool name：`eda_analysis`
- 入参：
  - `file_id`（必填）：用于定位要分析的数据
  - `session_id`（可选）：目前用于链路追溯（未来可用于上下文选择）
- 出参：Markdown 文本（直接作为对话消息返回）

## 5. 前后端联动流程

1. 前端上传 CSV 拿到 `file_id`
2. 前端发送对话消息到 `/api/v1/chat/messages`，携带 `fileId`
3. 后端调用大模型做意图识别，选择 `eda_analysis`
4. 后端通过 MCP 调用 `eda_analysis(file_id=...)`
5. MCP 从 MongoDB 拉取该 `file_id` 的时序数据并输出 EDA Markdown
6. 后端把结果作为 assistant 消息返回，前端直接渲染

## 6. 关键取舍与后续可优化点

- 取舍：没有要求用户配置“目标列/时间列”，而是采用自动选择（优先第一个数值列）来保证第四周闭环最短。
- 可优化：
  - 支持用户在对话中指定目标列（需要扩展 tool schema：`target_column`）
  - 对大数据量增加采样策略与统计优化（避免一次性拉全量）
  - 输出更丰富的可视化数据（例如 trend_data），并在前端绘图
