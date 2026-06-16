# 功能手册 06｜导出报告（export_markdown）

## 1. 目标与用户价值

导出报告用于把“对话驱动标准流程”的结果沉淀为可留档的产出：

- 用户得到一个独立的 Markdown 文件
- 文件包含数据集信息 + 每一步工具结果块 + 生成时间
- 便于复盘、分享、再加工（后续可扩展 PDF）

## 2. 复用 web 端后端的点（timewise-backend）

web 端有完整的“报告模块”概念：可以选择模块、生成报告、提供下载链接（见 [report.py](file:///d:/trae_workspace/github/timewise-backend/app/routers/report.py#L26-L79)）。

第四周复用的是其核心产品结构：

- 报告按模块组织（overview / eda / preprocessing / features / forecast）
- 报告生成有明确“生成时间”

同时做了第四周范围收敛：

- web 端最终导出是 PDF（reportlab），第四周只导出 Markdown
- web 端报告以 project 存储结构为中心，第四周以 `session_id + file_id` 为中心

## 3. 第四周实现位置（你应该看哪里）

- 报告拼装（Markdown 结构化）：[report.py](file:///d:/trae_workspace/data/file/fourth_week/code/analysis/report.py)
- MCP 工具导出实现（读取消息 tool_calls、写入文件）：[mcp_tools.py](file:///d:/trae_workspace/data/file/fourth_week/code/mcp_layer/tools/mcp_tools.py#L169-L223)
- tool_calls 的落库结构定义：[message.py](file:///d:/trae_workspace/data/file/fourth_week/code/models/message.py#L7-L12)

## 4. 接口定义（MCP 工具）

- Tool name：`export_markdown`
- 入参：
  - `session_id`（必填）：用来拉取该会话下的消息与工具调用记录
  - `file_id`（必填）：写入“数据集信息”模块
  - `scope`（可选，默认 `standard_flow`）：当前仅支持标准流程范围
- 出参：Markdown 文本（导出结果提示 + 生成文件路径）

导出文件落盘目录：

- `D:\trae_workspace\data\file\fourth_week\evidence\`

## 4.1 下载接口（REST）

为提升易用性，第四周新增了下载接口，用户无需手动去目录找文件：

- `GET /api/v1/sessions/{session_id}/files/{file_id}/report/download`

返回：

- 直接下载 Markdown 文件（浏览器下载/保存）

## 5. 前后端联动流程

1. 前端上传文件，得到 `file_id`
2. 用户按标准流程触发多个工具调用（EDA/预处理/特征/预测等）
3. 用户发起“导出报告”意图
4. LLM 识别意图并选择 `export_markdown`
5. 后端补齐 `session_id/file_id` 调用 MCP
6. MCP 从 MongoDB `messages` 集合中读取 assistant 消息里的 `tool_calls.tool_result`，按步骤拼装 Markdown，并写入 `evidence/`
7. 返回导出路径给前端展示

## 6. 关键取舍与后续可优化点

- 取舍：第四周导出依赖“tool_calls 已落库”，因此只要主链路跑通、每步都记录 tool_calls，就能稳定导出。
- 可优化：
  - 报告模块选择（scope 扩展为标准流程 / 标准流程+对话总结）
  - 输出更稳定的标题层级（基于 tool_name 的映射表，而不是直接用 tool_name）
  - 后续可增加“下载接口”返回更友好的文件名（例如包含数据集名）

## 7. 需要你确认的点（如果要做增强）

如果你希望导出体验更产品化，我建议增加一个 REST 下载接口，例如：

- `GET /api/v1/sessions/{session_id}/report/download`

这样前端可以直接触发浏览器下载，而不需要用户手动去本地目录找文件。该改动会涉及后端新增接口与权限边界（虽然第四周不做登录），需要你确认后我再做。
