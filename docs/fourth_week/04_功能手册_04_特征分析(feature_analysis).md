# 功能手册 04｜特征分析（feature_analysis）

## 1. 目标与用户价值

特征分析用于回答“这条时间序列的主要特征是什么”，第四周聚焦可解释、依赖少的基础特征：

- 趋势（线性拟合 slope/intercept）
- 自相关（ACF）
- 滚动统计（最近窗口均值/标准差）

## 2. 复用 web 端后端的点（timewise-backend）

web 端特征模块很完整（趋势/季节性/ACF/PACF/FFT/小波等），对应实现：[features.py](file:///d:/trae_workspace/github/timewise-backend/app/routers/features.py)

第四周复用其中两类“低依赖、强解释”的核心思路：

- 趋势：用 `np.polyfit` 做线性趋势估计（web 端同样采用 polyfit，见 [features.py](file:///d:/trae_workspace/github/timewise-backend/app/routers/features.py#L137-L150)）
- 自相关：ACF 思路（web 端优先 statsmodels，否则退化到相关计算；第四周直接实现轻量 ACF）

同时做了范围收敛：

- 不引入 statsmodels/pywt/scipy 等额外依赖，保证环境可控
- 输出以 Markdown 的“结论+小表格”为主，优先支持对话展示与导出

## 3. 第四周实现位置（你应该看哪里）

- 特征计算与 Markdown 输出：[features.py](file:///d:/trae_workspace/data/file/fourth_week/code/analysis/features.py)
- 数据加载：[data.py](file:///d:/trae_workspace/data/file/fourth_week/code/analysis/data.py#L10-L28)
- MCP 工具封装入口：[mcp_tools.py](file:///d:/trae_workspace/data/file/fourth_week/code/mcp_layer/tools/mcp_tools.py#L141-L148)

## 4. 接口定义（MCP 工具）

- Tool name：`feature_analysis`
- 入参：
  - `file_id`（必填）
  - `session_id`（可选）
- 出参：Markdown 文本

## 5. 前后端联动流程

1. 前端上传拿到 `file_id`
2. 用户在对话中提出“特征/趋势/相关性”等意图（不要求固定句式）
3. LLM 识别意图，选择 `feature_analysis`
4. 后端补齐 `file_id/session_id` 调用 MCP
5. MCP 输出特征结论 Markdown，前端直接展示

## 6. 关键取舍与后续可优化点

- 取舍：第四周把“特征分析”定义为“能解释、能导出、能复现”的最小集合，不追求频域/小波等高级特征。
- 可优化：
  - 增加季节性强度评估（web 端已有思路，可按需迁移）
  - 增加 PACF（需要 statsmodels 或自实现）
  - 输出更多结构化数据给前端绘图（比如 ACF 全量数组）
