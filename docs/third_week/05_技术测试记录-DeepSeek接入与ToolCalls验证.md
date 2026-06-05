# 第三周技术测试记录：DeepSeek 接入与 Tool Calls 验证

## 1. 目的

本测试用于证明第三周“真实大模型 + MCP 工具调用 + MongoDB 持久化 + API 可回放”的端到端链路已跑通，且当前项目已切换到 DeepSeek（OpenAI 兼容模式）并能稳定产生 `tool_calls`。

## 2. 测试范围（本次验证覆盖的能力）

- 大模型路由：用户自然语言 → 选择工具（`eda_analysis / preprocessing / feature_analysis / forecast`）→ 生成结构化参数
- MCP 工具调用：后端根据工具选择调用 MCP tool，并获得工具输出
- MongoDB 落库：用户消息、助手消息、`toolCalls`（驼峰字段）写入 `messages` 集合
- API 可回放：可通过 `GET /api/v1/sessions/{session_id}/messages` 拉取全历史，并读到 `tool_calls`
- 费用侧证据：DeepSeek 平台用量增长

## 3. 为什么要这样测（验证原因）

### 3.1 为什么不能只看“前端有回复”

前端能看到回复并不能证明：

- 一定调用了真实大模型（可能走规则匹配或其他兜底）
- 一定发生了 tool calling（模型可能直接文本回答）
- tool_calls 一定被写入 Mongo 并可回放

因此必须用“接口返回 + 历史回放 + 数据库存证”三层证据来闭环。

### 3.2 为什么看 `tool_calls` 就能证明“LLM tool calling 成功”

在本项目中：

- LLM（DeepSeek）负责“选择工具 + 给出参数”
- MCP 工具负责“真正产生分析结果文本”

因此一旦在 assistant 消息中看到：

- `tool_calls[0].tool_name` 为预期工具名（如 `eda_analysis`、`forecast`）
- `tool_calls[0].tool_args` 与用户意图一致（如 `model=prophet, periods=30`）
- `tool_calls[0].tool_result` 为 MCP 返回的分析结果文本

即可证明：LLM→ToolCall 解析成功，且 MCP 调用成功，并且结果已被后端统一封装与返回。

## 4. 测试前置条件

### 4.1 服务状态

- 后端已启动：`http://localhost:8000`
- 前端已启动：`http://localhost:5173`
- MongoDB 已启动（本地）

后端启动命令（实测使用）：

```powershell
cd D:\trae_workspace\data\file\third_week\code
D:\Annaconda\envs\hongsu-mcp\python.exe -m uvicorn backend:app --host 127.0.0.1 --port 8000
```

### 4.2 环境与依赖

建议使用 conda 环境 `hongsu-mcp` 运行后端与测试命令（避免出现 `ModuleNotFoundError: fastapi` 之类的问题）。

### 4.3 关键配置（已验证生效）

在 `D:\trae_workspace\data\file\third_week\code\.env`：

- `OPENAI_API_KEY=我的_deepseek_key`
- `OPENAI_BASE_URL=https://api.deepseek.com`
- `OPENAI_MODEL=deepseek-v4-pro`（本次验证使用）

## 5. 中文乱码问题（重要）

### 5.1 现象

在 PowerShell 中将返回体 `ConvertTo-Json` 输出到终端时，中文可能出现 `ãæ...` 或 `?????` 等乱码。

### 5.2 原因

这是终端显示编码问题（PowerShell 输出编码/当前终端编码与 UTF-8 不一致），并不代表接口返回的数据本身是乱码。通常：

- 浏览器 Network 面板 / MongoDB Compass 显示正常
- PowerShell 终端显示异常

### 5.3 解决方法（推荐其一即可）

方法 A：在当前 PowerShell 会话里切换输出编码为 UTF-8

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
```

方法 B：切换代码页（部分机器有效）

```powershell
chcp 65001
```

方法 C：用浏览器 Network 的 Response 查看（最稳定）

由于浏览器会按正确的 UTF-8 解码显示，适合截图留档。

## 6. 验证流程（完整闭环）

说明：以下命令均在 PowerShell 中执行，推荐在目录 `D:\trae_workspace\data\file\third_week\code` 下执行。

### 6.1 第 0 步：确认配置被正确读取（最小验证）

```powershell
D:\Annaconda\envs\hongsu-mcp\python.exe -c "from config import settings; print(bool(settings.openai_api_key), settings.openai_base_url, settings.openai_model)"
```

终端实测输出：

```text
True https://api.deepseek.com deepseek-v4-pro
```

判定成功原因：

- `True` 表示已读取到 key（不会打印 key 本身）
- base_url 指向 `api.deepseek.com` 表示当前 OpenAI SDK 实际调用 DeepSeek
- model 为 `deepseek-v4-pro` 表示已切换到指定模型

### 6.2 第 1 步：发送“数据概览”请求（验证 eda_analysis 路由）

```powershell
[Console]::OutputEncoding=[System.Text.Encoding]::UTF8
$OutputEncoding=[System.Text.Encoding]::UTF8

$bodyObj=@{
  content    = "请帮我做一下探索性数据分析，做一下数据概览"
  session_id = $null
  fileId     = $null
}

$body=$bodyObj | ConvertTo-Json
$wr=Invoke-WebRequest -Method Post -Uri "http://127.0.0.1:8000/api/v1/chat/messages" -ContentType "application/json" -Body $body
$ms=New-Object System.IO.MemoryStream
$wr.RawContentStream.CopyTo($ms)
$jsonText=[System.Text.Encoding]::UTF8.GetString($ms.ToArray())
$resp=$jsonText | ConvertFrom-Json

$tool=$resp.data.tool_calls[0]
$out=@{
  success=$resp.success
  session_id=$resp.data.session_id
  tool_name=$tool.tool_name
  tool_args=$tool.tool_args
  tool_result_head=$tool.tool_result.Substring(0,[Math]::Min(160,$tool.tool_result.Length))
}
$out | ConvertTo-Json -Depth 20
```

终端实测输出（摘要）：

```json
{
  "tool_result_head": "【探索性数据分析（EDA）结果】\n数据集：sales_data\n\n 数据概览：\n- 数据形状：(1000, 15)\n- 时间范围：2024-01-01 至 2026-05-18\n- 采样频率：每日\n\n缺失值统计：\n- 列A：0.5%\n- 列B：2.3%\n- 其他列：0%\n\n基本统计量：\n- 均值：1234.56\n- 中位",
  "tool_name": "eda_analysis",
  "session_id": "6a211ab2fa1e02e90913e7bb",
  "success": true,
  "tool_args": {
    "data_name": "sales_data"
  }
}
```

判定成功原因：

- `tool_name=eda_analysis`：证明 LLM 将“概览/数据概况”识别为 EDA 意图并选择了正确工具
- `tool_args` 为结构化 JSON：证明 tool calling 解析成功
- `tool_result` 非空：证明 MCP 工具成功执行并返回结果
- `session_id` 返回：证明会话被创建/复用，可用于拉取历史回放

### 6.3 第 2 步：用 session_id 拉取历史（验证可回放）

```powershell
[Console]::OutputEncoding=[System.Text.Encoding]::UTF8
$OutputEncoding=[System.Text.Encoding]::UTF8

$sessionId="6a211ab2fa1e02e90913e7bb"
$wr=Invoke-WebRequest -Method Get -Uri "http://127.0.0.1:8000/api/v1/sessions/$sessionId/messages"
$ms=New-Object System.IO.MemoryStream
$wr.RawContentStream.CopyTo($ms)
$jsonText=[System.Text.Encoding]::UTF8.GetString($ms.ToArray())
$history=$jsonText | ConvertFrom-Json

$assistant=$history.data | Where-Object { $_.role -eq "assistant" } | Select-Object -First 1
$tool=$assistant.tool_calls[0]
$out=@{
  success=$history.success
  message_count=($history.data | Measure-Object).Count
  first_roles=($history.data | Select-Object -First 2 -ExpandProperty role)
  assistant_tool_name=$tool.tool_name
  assistant_tool_args=$tool.tool_args
}
$out | ConvertTo-Json -Depth 20
```

终端实测输出（摘要）：

```json
{
  "message_count": 2,
  "assistant_tool_name": "eda_analysis",
  "first_roles": [
    "user",
    "assistant"
  ],
  "success": true,
  "assistant_tool_args": {
    "data_name": "sales_data"
  }
}
```

判定成功原因：

- 证明消息已落库且接口可读取
- 证明 `tool_calls` 不仅在发送接口返回里存在，也能作为历史被回放（可用于审计与复盘）

### 6.4 第 3 步：发送“预测 30 天”请求（验证 forecast 路由与参数）

```powershell
[Console]::OutputEncoding=[System.Text.Encoding]::UTF8
$OutputEncoding=[System.Text.Encoding]::UTF8

$bodyObj=@{
  content    = "请用 prophet 做预测，预测未来 30 天"
  session_id = "6a211ab2fa1e02e90913e7bb"
  fileId     = $null
}

$body=$bodyObj | ConvertTo-Json
$wr=Invoke-WebRequest -Method Post -Uri "http://127.0.0.1:8000/api/v1/chat/messages" -ContentType "application/json" -Body $body
$ms=New-Object System.IO.MemoryStream
$wr.RawContentStream.CopyTo($ms)
$jsonText=[System.Text.Encoding]::UTF8.GetString($ms.ToArray())
$resp2=$jsonText | ConvertFrom-Json

$tool=$resp2.data.tool_calls[0]
$out=@{
  success=$resp2.success
  session_id=$resp2.data.session_id
  tool_name=$tool.tool_name
  tool_args=$tool.tool_args
  tool_result_head=$tool.tool_result.Substring(0,[Math]::Min(160,$tool.tool_result.Length))
}
$out | ConvertTo-Json -Depth 20
```

终端实测输出（摘要）：

```json
{
  "tool_result_head": "【时间序列预测结果】\n数据集：sales_data\n预测模型：Prophet\n预测期数：30天\n\n模型评估：\n- MAE（平均绝对误差）：123.45\n- MAPE（平均绝对百分比误差）：8.5%\n- RMSE（均方根误差）：156.78\n- R²（决定系数）：0.89\n\n预测结果（未来30天）：\n日期        ",
  "tool_name": "forecast",
  "session_id": "6a211ab2fa1e02e90913e7bb",
  "success": true,
  "tool_args": {
    "data_name": "sales_data",
    "model": "prophet",
    "periods": 30
  }
}
```

判定成功原因：

- 与第 1 步相比工具名发生变化（`eda_analysis` → `forecast`），证明路由并非固定写死
- `model=prophet, periods=30` 能体现大模型对自然语言参数的抽取能力

### 6.5 第 4 步：再次拉取历史（证明多轮均可回放）

```powershell
[Console]::OutputEncoding=[System.Text.Encoding]::UTF8
$OutputEncoding=[System.Text.Encoding]::UTF8

$sessionId="6a211ab2fa1e02e90913e7bb"
$wr=Invoke-WebRequest -Method Get -Uri "http://127.0.0.1:8000/api/v1/sessions/$sessionId/messages"
$ms=New-Object System.IO.MemoryStream
$wr.RawContentStream.CopyTo($ms)
$jsonText=[System.Text.Encoding]::UTF8.GetString($ms.ToArray())
$history2=$jsonText | ConvertFrom-Json

$toolNames=@($history2.data | Where-Object { $_.role -eq "assistant" } | ForEach-Object { $_.tool_calls[0].tool_name })
$out=@{
  success=$history2.success
  message_count=($history2.data | Measure-Object).Count
  assistant_tool_names=$toolNames
}
$out | ConvertTo-Json -Depth 10
```

终端实测输出（摘要）：

```json
{
  "message_count": 4,
  "assistant_tool_names": [
    "eda_analysis",
    "forecast"
  ],
  "success": true
}
```

判定成功原因：

说明会话内多轮消息与 tool_calls 均被持久化，并可按时间顺序回放。

### 6.6 第 5 步（最权威存证）：MongoDB 落库验证（终端脚本）

MongoDB 内实际存储字段为驼峰：`toolCalls`，集合为 `timewise.messages`。

终端验证命令（pymongo）：

```powershell
D:\Annaconda\envs\hongsu-mcp\python.exe -c "from config import settings; from pymongo import MongoClient; from bson import ObjectId; client=MongoClient(settings.mongodb_uri); db=client[settings.mongodb_db_name]; sid=ObjectId('6a211ab2fa1e02e90913e7bb'); docs=list(db.messages.find({'sessionId':sid}).sort('timestamp',1)); assistants=[d for d in docs if d.get('role')=='assistant']; tool_names=[a.get('toolCalls',[{}])[0].get('tool_name') for a in assistants]; keys=list(assistants[0].get('toolCalls',[{}])[0].keys()) if assistants else []; print('message_count', len(docs)); print('assistant_tool_names', tool_names); print('toolCalls_keys', keys)"
```

终端实测输出：

```text
message_count 4
assistant_tool_names ['eda_analysis', 'forecast']
toolCalls_keys ['tool_name', 'tool_args', 'tool_result', 'timestamp']
```

判定成功原因：

数据库侧证据证明：即使前端/接口层不可用，核心数据仍可追溯与复盘，满足“工程可验证性”。

### 6.7 第 6 步（费用侧证据）：DeepSeek 用量页验证

在完成第 1/3 步后，打开并刷新 DeepSeek Usage 页面，确认用量有增长（可截图留存用于报销/汇报）：

https://platform.deepseek.com/usage

## 7. 本次测试输出结果摘要（结论）

本次实测已验证：

- DeepSeek 配置已生效（key_loaded=True，base_url 指向 DeepSeek）
- EDA 需求：产生 `tool_calls.tool_name=eda_analysis` 且有 `tool_result`
- 预测需求：产生 `tool_calls.tool_name=forecast`，并正确抽取 `model=prophet, periods=30`
- 同一 session 的历史可通过接口回放，assistant 消息包含 `tool_calls`
- MongoDB `messages.toolCalls` 字段存在（可通过 Compass 查看）

以上证据链可以直接证明：第三周“真实大模型 + MCP 工具 + MongoDB”端到端闭环已跑通。
