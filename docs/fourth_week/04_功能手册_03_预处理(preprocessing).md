# 功能手册 03｜预处理（preprocessing）

## 1. 目标与用户价值

预处理用于把数据从“可读”变为“可分析”，第四周只保留最小、可回归的三种方式：

- `missing_fill`：缺失值填充
- `outlier_remove`：异常值移除（zscore 3σ，且会先进行缺失值填充）
- `type_convert`：类型转换（尽量把列转为数值）

输出以“处理摘要”为主，确保用户能理解发生了什么变化。

## 2. 复用 web 端后端的点（timewise-backend）

web 端预处理模块覆盖面很广（重采样、噪声滤波、孤立森林等），对应实现：[preprocessing.py](file:///d:/trae_workspace/github/timewise-backend/app/routers/preprocessing.py)

第四周复用的是其中最稳定、依赖最少、且能支撑闭环的子集：

- 缺失值处理的基本方法（ffill/bfill/mean 思路）
- zscore 异常值识别与处理思路（remove/clip/smooth 等中的 remove 子集）

并做了范围收敛：

- 不引入 sklearn/filterpy 等重依赖
- 不做复杂配置面板，只通过对话意图触发

## 3. 第四周实现位置（你应该看哪里）

- 预处理核心实现与 Markdown 摘要：[preprocess.py](file:///d:/trae_workspace/data/file/fourth_week/code/analysis/preprocess.py)
- 数据加载（MongoDB -> DataFrame）：[data.py](file:///d:/trae_workspace/data/file/fourth_week/code/analysis/data.py#L10-L28)
- MCP 工具封装入口：[mcp_tools.py](file:///d:/trae_workspace/data/file/fourth_week/code/mcp_layer/tools/mcp_tools.py#L129-L139)

## 4. 接口定义（MCP 工具）

- Tool name：`preprocessing`
- 入参：
  - `file_id`（必填）
  - `method`（可选，默认 `missing_fill`）：`missing_fill | outlier_remove | type_convert`
  - `session_id`（可选）
- 出参：Markdown 文本（处理摘要）

## 5. 前后端联动流程

与 EDA 相同的主链路：

1. 前端上传得到 `file_id`
2. 前端对话触发“预处理意图”
3. LLM 识别后选择 `preprocessing` 并给出 `method`
4. 后端补齐 `file_id/session_id` 后调用 MCP
5. MCP 输出预处理摘要（当前版本不落库新数据版本，仅输出结果）

## 6. 关键取舍与需要你确认的点

### 6.1 当前行为（第四周已支持“下载处理后数据”）

- 预处理会生成一个“处理后 CSV 文件”，并归档到 `fourth_week/evidence/`
- 对话会返回本地路径与下载地址（REST），用户可直接下载处理后的数据
- 当前版本仍不把“处理后数据版本”写回 MongoDB 的 `time_series_data`（即分析步骤默认仍基于原始数据）

### 6.2 如果你希望更贴近 web 端形态（需要你确认后我再做）

我可以把预处理升级为“生成处理后数据版本”，两种方式：

1. 写入同一个 `time_series_data`，但增加 `metadata.version` 或 `metadata.stage=preprocessed`
2. 新建集合 `time_series_data_processed`，按 `file_id` + `version` 关联

这会影响后续 EDA/特征/预测的“读哪个版本”，需要你确认选择哪一种版本管理方式再做。
