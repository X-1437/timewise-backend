# 功能手册 05｜朴素预测（naive_forecast）

## 1. 目标与用户价值

朴素预测是“基线预测”，用于：

- 给用户一个最低成本的预测参考
- 给后续可能加入的机器学习模型提供对比基线

第四周明确不追求复杂模型，只提供三个朴素方法：

- `next_row`：用上一条作为下一条预测（最常见基线）
- `same_time`：用前 7 条之前的值作为当前预测（可理解为“周期=7”的平移基线）
- `daily_sum`：按 7 条窗口累加后再做平移预测（适合日汇总类直觉）

## 2. 复用 web 端后端的点（timewise-backend）

该功能的预测方法与评估指标，直接复用了 web 端的朴素预测实现与口径：

- 方法定义与 options：见 [forecast.py](file:///d:/trae_workspace/github/timewise-backend/app/routers/forecast.py#L28-L36)
- 预测生成逻辑与 MAE/MSE/RMSE/MAPE：见 [forecast.py](file:///d:/trae_workspace/github/timewise-backend/app/routers/forecast.py#L80-L124)

第四周的主要改造点：

- web 端是“读取上传文件路径并做回测”；第四周改为“从 MongoDB 时序集合按 `file_id` 拉取数据再回测”
- 输出改为 Markdown（便于对话展示与导出），并额外补了“未来 N 步的朴素延续预测”（基于最后一个值延续），用于满足用户对“未来预测步数”的直觉期待

## 3. 第四周实现位置（你应该看哪里）

- 朴素预测核心实现：[naive_forecast.py](file:///d:/trae_workspace/data/file/fourth_week/code/analysis/naive_forecast.py)
- MCP 工具封装入口：[mcp_tools.py](file:///d:/trae_workspace/data/file/fourth_week/code/mcp_layer/tools/mcp_tools.py#L150-L167)

## 4. 接口定义（MCP 工具）

- Tool name：`naive_forecast`
- 入参：
  - `file_id`（必填）
  - `method`（可选，默认 `next_row`）：`next_row | same_time | daily_sum`
  - `periods`（可选，默认 7）：未来预测步数
  - `session_id`（可选）
- 出参：Markdown 文本，包含回测指标、回测样例、未来预测表

## 5. 前后端联动流程

与其他分析工具一致：

1. 前端上传得到 `file_id`
2. 用户以任意自然语言表达“想要简单预测/基线预测”
3. LLM 识别意图并选择 `naive_forecast`，可附带 method/periods
4. 后端补齐 `file_id/session_id` 后调用 MCP
5. MCP 输出 Markdown，前端展示并可被导出汇总

## 6. 关键取舍与需要你确认的点

### 6.1 当前默认行为

- 回测方法用于评估基线“拟合程度”（用历史预测历史）
- 未来预测部分用“最后一个值延续”作为最朴素的未来预测

### 6.2 是否需要“指定目标列”能力（需要你确认后我再做）

当前默认自动选第一个数值列作为目标列。如果你希望用户可在对话里说：

- “对 sales 列做预测”
- “用 amount 做预测”

则需要扩展工具 schema 增加 `target_column`，并在 LLM prompt 中加入约束与示例。
