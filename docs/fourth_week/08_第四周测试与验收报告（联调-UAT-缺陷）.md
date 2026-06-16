# 第四周测试与验收报告（联调-UAT-缺陷）

## 1. 测试概述

- 项目：鸿溯 - 时间序列数据分析助手
- 周次目标：核心协议与链路打通（上传 → 对话触发 → MCP 工具调用 → 结果返回 → 导出报告）
- 测试类型：联调测试 + 回归测试 + UAT（人工验收）+ 缺陷闭环
- 测试口径依据：
  - [05_第四周回归与验收清单.md](file:///D:/trae_workspace/data/file/fourth_week/05_%E7%AC%AC%E5%9B%9B%E5%91%A8%E5%9B%9E%E5%BD%92%E4%B8%8E%E9%AA%8C%E6%94%B6%E6%B8%85%E5%8D%95.md)
  - [02_第四周需求规格说明书.md](file:///D:/trae_workspace/data/file/fourth_week/02_%E7%AC%AC%E5%9B%9B%E5%91%A8%E9%9C%80%E6%B1%82%E8%A7%84%E6%A0%BC%E8%AF%B4%E6%98%8E%E4%B9%A6.md)

## 2. 测试环境

- 前端：`D:\trae_workspace\data\file\second_week\frontend`（Vite/React）
  - 访问：`http://localhost:5173/`
- 后端：`D:\trae_workspace\data\file\fourth_week\code`（FastAPI）
  - 访问：`http://127.0.0.1:8000/docs`
  - 核心接口：
    - `POST /api/v1/sessions`
    - `POST /api/v1/files/upload`
    - `POST /api/v1/chat/messages`
    - `GET /api/v1/sessions/{session_id}/messages`
    - `GET /api/v1/sessions/{session_id}/files/{file_id}/preprocessed/download`
    - `GET /api/v1/sessions/{session_id}/files/{file_id}/report/download`
- 数据库：MongoDB（本地）
- 工具链：MCP（stdio）

## 3. 测试数据

- 脏数据样例：`D:\trae_workspace\data\file\fourth_week\test_data\test_sales_dirty.csv`
  - 特征：含缺失值（空 sales）+ 极端异常值（999999）

## 4. 验收场景与执行记录（UAT）

### 4.1 场景 A：完整闭环（主链路）

| 步骤 | 用户输入（自然语言） | 期望触发工具 | 实际结果 | 证据 |
|---|---|---|---|---|
| 1 | 上传 `test_sales_dirty.csv` | upload 接口 | 通过 | 见第 5 节 |
| 2 | 请先帮我清洗一下这个数据 | `preprocessing` | 通过 | 预处理文件下载链接可用 |
| 3 | 帮我简单分析一下这个数据，方便我更了解 | `eda_analysis` | 通过 | 返回 EDA Markdown |
| 4 | 分析一下这个数据具有哪些特征 | `feature_analysis` | 通过 | 返回特征分析 Markdown |
| 5 | 进行一下朴素预测 | `naive_forecast` | 通过 | 返回预测结果 Markdown |
| 6 | 帮我生成分析报告 | `export_markdown` | 通过 | 报告下载链接可用 |

### 4.2 场景 B：重复执行回归（稳定性）

- 同一会话内重复执行“清洗步骤”两次，均可生成可下载的预处理文件，路径与时间戳不同，下载接口稳定返回 `200`。

## 5. 证据归档（evidence）

### 5.1 本次验收会话标识

- session_id：`6a2a4edbb08b7995216df6eb`
- file_id：`6a2a4ec1b08b7995216df6e0`

### 5.2 预处理产物

- 文件（示例）：
  - `D:\trae_workspace\data\file\fourth_week\evidence\preprocessed_6a2a4ec1b08b7995216df6e0_20260611T055955Z.csv`
  - `D:\trae_workspace\data\file\fourth_week\evidence\preprocessed_6a2a4ec1b08b7995216df6e0_20260611T060008Z.csv`
- 下载（示例）：
  - `/api/v1/sessions/6a2a4edbb08b7995216df6eb/files/6a2a4ec1b08b7995216df6e0/preprocessed/download`

### 5.3 报告产物

- 报告文件：
  - `D:\trae_workspace\data\file\fourth_week\evidence\report_6a2a4edbb08b7995216df6eb_20260611T060340Z.md`
- 下载：
  - `/api/v1/sessions/6a2a4edbb08b7995216df6eb/files/6a2a4ec1b08b7995216df6e0/report/download`

## 6. 缺陷清单（发现-修复-回归）

### 6.1 已关闭缺陷

| ID | 严重级别 | 标题 | 影响 | 复现步骤 | 修复结果 |
|---|---|---|---|---|---|
| BUG-01 | P1 | 右侧栏不展示最终导出报告预览 | 用户无法在产品内回看报告内容 | 生成报告后观察右侧栏 | 已修复：导出后自动拉取报告内容并在右侧栏展示 |
| BUG-02 | P1 | 右侧“导出预览报告”按钮无法直接下载报告 | 导出体验断裂，需要手动复制链接 | 点击按钮无下载 | 已修复：按钮支持“生成并下载 / 直接下载” |
| BUG-03 | P2 | 右侧栏只展示最新一步结果，不保留历史步骤 | 用户无法对比清洗/EDA/特征/预测的阶段结果 | 依次执行多步后观察右侧栏 | 已修复：按步骤累积展示（结果历史列表） |
| BUG-04 | P2 | 聊天输出含 `#` 等 Markdown 符号影响可读性 | 阅读成本高 | 任意返回 Markdown 时观察 | 已修复：聊天区与右侧栏支持基础 Markdown 渲染 |

### 6.2 待确认项（非阻断）

| ID | 严重级别 | 标题 | 说明 | 建议 |
|---|---|---|---|---|
| TODO-01 | P3 | 预测指标在异常值场景下数值极端（mape 很大） | 数据本身含极端异常值，基线模型指标会被放大 | 第五周做算法校验与更合理的异常值策略/指标口径说明 |

## 7. 测试结论

- 第四周核心链路（上传/对话触发/工具调用/结果返回/导出与下载）已通过联调与人工验收。
- 前端右侧栏已具备“步骤结果沉淀 + 报告一键下载”的最小闭环能力，符合第四周可演示/可验收口径。

