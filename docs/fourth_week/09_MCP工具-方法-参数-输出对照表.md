# MCP 工具-方法-参数-输出对照表（第四周）

本文档用于把“对话意图 → MCP 工具 → 参数方法 → 输出结构”统一到一张表，便于：

- 产品/研发/测试对齐工具能力边界
- 形成可复用的测试用例与验收口径
- 支撑第五周算法校验与预览区体验优化

代码依据：[mcp_tools.py](file:///D:/trae_workspace/data/file/fourth_week/code/mcp_layer/tools/mcp_tools.py)

## 1. 工具总览（6 个）

| 工具名 | 一句话用途 | 是否有 method/scope | 默认值 |
|---|---|---:|---|
| `upload_data` | 确认当前文件、输出文件信息与数据样例 | 否 | - |
| `eda_analysis` | EDA 概览/缺失/统计/异常提示 | 否 | - |
| `preprocessing` | 预处理：缺失填充/异常移除/类型转换 + 生成可下载 CSV | 是（method） | `missing_fill` |
| `feature_analysis` | 特征分析：趋势/自相关/滚动统计 | 否 | - |
| `naive_forecast` | 朴素预测：基线回测指标 + 未来预测 | 是（method） | `next_row` |
| `export_markdown` | 导出 Markdown 报告 + 生成下载链接 | 是（scope，但当前只有 1 种） | `standard_flow` |

## 2. 逐工具对照（含“方法/口令/输出”）

### 2.1 `upload_data`

- **用途**：确认数据文件并展示文件信息与数据样例（前 5 行）
- **输入参数**
  - `file_id`（必填）
  - `session_id`（可选）
- **可选方法**：无
- **典型触发口令（自然语言示例）**
  - “确认一下当前文件信息”
  - “用的是哪个文件？”
  - “看看文件信息/数据集信息”
- **输出结构（Markdown）**
  - 标题：`## 数据文件已确认`
  - 文件信息块（file_id、文件名、行数/列数、列名等）
  - 数据样例表格（前 5 行）

### 2.2 `eda_analysis`

- **用途**：探索性数据分析（EDA）：数据规模、时间范围、缺失值、基本统计量
- **输入参数**
  - `file_id`（必填）
  - `session_id`（可选）
- **可选方法**：无
- **典型触发口令**
  - “帮我简单分析一下这个数据”
  - “先看下数据整体怎么样”
  - “数据概览/基本情况”
- **输出结构（Markdown）**
  - 数据概览（行/列/时间范围/目标列）
  - 缺失值表格
  - 数值统计表格

### 2.3 `preprocessing`

- **用途**：数据预处理 + 生成“预处理后 CSV 文件”并给出下载链接
- **输入参数**
  - `file_id`（必填）
  - `session_id`（可选；若提供则会生成下载链接）
  - `method`（可选；默认 `missing_fill`）
- **方法枚举（method=3 种）**
  - `missing_fill`：缺失值填充（默认）
  - `outlier_remove`：异常值移除（实现中会先填缺失再移除异常）
  - `type_convert`：类型规范化（如可解析为数值则转为数值）
- **典型触发口令**
  - “请先帮我清洗一下这个数据”（通常会落到 `outlier_remove`）
  - “把缺失值先处理一下”（通常会落到 `missing_fill`）
  - “做一下预处理”
- **输出结构（Markdown）**
  - 标题：`## 预处理结果`
  - 方法说明与摘要（处理前/后行数、移除异常行数、缺失值变化）
  - 列信息（列数/列名）
  - 预处理文件
    - 本地路径：`D:\trae_workspace\data\file\fourth_week\evidence\preprocessed_*.csv`
    - 下载链接：`/api/v1/sessions/{session_id}/files/{file_id}/preprocessed/download`

### 2.4 `feature_analysis`

- **用途**：基础特征分析：趋势、自相关（ACF）、滚动统计
- **输入参数**
  - `file_id`（必填）
  - `session_id`（可选）
- **可选方法**：无
- **典型触发口令**
  - “分析一下这个数据具有哪些特征”
  - “看看趋势和相关性”
  - “特征分析/相关性分析”
- **输出结构（Markdown）**
  - 目标列信息
  - 趋势（线性拟合 slope/intercept）
  - 自相关表格（ACF）
  - 滚动统计（窗口=7 的均值/标准差等）

### 2.5 `naive_forecast`

- **用途**：朴素预测（基线）+ 回测指标 + 未来预测结果
- **输入参数**
  - `file_id`（必填）
  - `session_id`（可选）
  - `method`（可选；默认 `next_row`）
  - `periods`（可选；默认 `7`）
- **方法枚举（method=3 种）**
  - `next_row`：前值延续（默认）
  - `same_time`：同一时刻/同周期对齐（取历史对应点）
  - `daily_sum`：按天聚合后的基线外推（适用于更长粒度）
- **典型触发口令**
  - “进行一下朴素预测”
  - “给我一个简单基准预测”
  - “预测未来 7 天/未来几步”
- **输出结构（Markdown）**
  - 回测指标表格（mae/mse/rmse/mape 等）
  - 回测样例表格（actual vs predicted）
  - 未来预测表格（step/predicted）

### 2.6 `export_markdown`

- **用途**：导出 Markdown 报告（汇总本次会话内已产生的步骤结果）并给出下载链接
- **输入参数**
  - `session_id`（必填）
  - `file_id`（必填）
  - `scope`（可选；默认 `standard_flow`）
- **方法/范围枚举**
  - `scope=standard_flow`（当前唯一）
- **典型触发口令**
  - “帮我生成分析报告”
  - “把这次分析导出成报告”
  - “导出报告/生成报告”
- **输出结构（Markdown）**
  - 标题：`## 导出完成`
  - 本地路径：`D:\trae_workspace\data\file\fourth_week\evidence\report_*.md`
  - 下载链接：`/api/v1/sessions/{session_id}/files/{file_id}/report/download`

## 3. 与前端字段对齐（关键点）

前端请求体字段名为 `fileId`，后端会映射到 `file_id`（alias），详见第四周联调口径：

- 请求：`POST /api/v1/chat/messages`
  - `content`
  - `session_id`
  - `fileId`（前端字段）

## 4. 测试用例生成建议（如何把表变成用例）

- 每个工具至少 1 条“主路径”用例
- 有 method 的工具（`preprocessing` / `naive_forecast`）每个 method 至少 1 条用例
- 导出用例必须验证：
  - 下载接口 200
  - 文件内容可读（UTF-8）
  - 报告包含“数据集信息/步骤结果/生成时间”

