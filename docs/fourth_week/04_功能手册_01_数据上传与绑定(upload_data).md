# 功能手册 01｜数据上传与绑定（upload_data）

## 1. 目标与用户价值

该功能解决两件事：

- 用户上传 CSV 后，系统能把数据写入数据库并生成 `file_id`
- 用户在对话里可以“确认当前使用的是哪个文件”，并看到文件信息与数据样例，避免后续分析跑错数据

## 2. 复用 web 端后端的点（timewise-backend）

web 端后端的“数据接入”是围绕项目（project）上传文件、再读取文件做分析（见 [timewise-backend README](file:///d:/trae_workspace/github/timewise-backend/README.md#L82-L100)）。

第四周没有直接复用它的“项目+文件路径读取”模式，而是复用了它的核心思想：

- “先明确数据对象，再做分析”
- 在导出报告时把“数据概览/模块结果”按模块组织（与 report 模块化思路一致：[report.py](file:///d:/trae_workspace/github/timewise-backend/app/routers/report.py#L26-L37)）

同时，第四周阶段代码使用了 MongoDB 时序集合存储（`time_series_data`），与 web 端“时序集合”方向一致（见 [timewise-backend README](file:///d:/trae_workspace/github/timewise-backend/README.md#L95-L101)）。

## 3. 第四周实现位置（你应该看哪里）

- 文件上传 REST 接口：[files.py](file:///d:/trae_workspace/data/file/fourth_week/code/api/files.py#L10-L25)
- CSV 入库逻辑（写入 MongoDB `time_series_data`）：[file_service.py](file:///d:/trae_workspace/data/file/fourth_week/code/services/file_service.py#L17-L76)
- MCP 工具（用于“确认文件/展示样例”）：[mcp_tools.py](file:///d:/trae_workspace/data/file/fourth_week/code/mcp_layer/tools/mcp_tools.py#L74-L116)

## 4. 接口定义（前后端怎么对齐）

### 4.1 上传接口（前端调用）

- Method：POST
- Path：`/api/v1/files/upload`
- Content-Type：`multipart/form-data`
- 参数：
  - `file`：CSV 文件
  - `session_id`（可选）：把文件与会话绑定
- 返回：统一 envelope（`success/data/message/error_code`），`data` 内包含 `id`（即 `file_id`）、`inserted_rows` 等

### 4.2 绑定/确认工具（后端内部：MCP）

- Tool name：`upload_data`
- 入参 schema（核心字段）：
  - `session_id`（可选）
  - `file_id`（必填）
- 输出：Markdown 文本，包含文件信息与前 5 行数据样例

说明：这里的 `upload_data` 不是“真正执行上传”（上传发生在 REST），而是“对话侧确认当前数据文件上下文”的工具语义。

## 5. 前后端联动流程（你可以按这个理解）

1. 前端调用 `/files/upload` 上传 CSV，得到 `file_id`
2. 前端在后续发送消息时，把 `fileId` 带到 `/chat/messages`（见前端调用：[api.ts](file:///d:/trae_workspace/data/file/second_week/frontend/src/services/api.ts#L37-L59)）
3. 后端 `ChatService` 识别到用户想“确认文件”时，会触发 MCP 的 `upload_data` 工具，并自动把 `file_id` 补齐后调用（见 [chat_service.py](file:///d:/trae_workspace/data/file/fourth_week/code/services/chat_service.py#L42-L67)）
4. MCP 工具从 `files` 与 `time_series_data` 读取信息，返回 Markdown 给前端展示

## 6. 关键取舍与后续可优化点

- 取舍：第四周没有复用 web 端“project_id + data_config”体系，而采用 `file_id` 作为最小数据锚点，目的是让闭环更短、更易跑通。
- 可优化：
  - 增加“选择文件/切换文件”能力（当用户上传多个文件时）
  - 把 `upload_data` 改为可返回“可用文件列表”并让 LLM 选择（需要扩展 schema）
