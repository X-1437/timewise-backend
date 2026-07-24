# Timewise Backend

`timewise-backend` 是“时间序列数据分析助手”项目的后端仓库。

本仓库当前承载两类内容：
- 原有 Web 形态后端基础：`app/`
- 当前正式交付的对话式 MCP 后端主线：`mcp/src/`

因此，这不是一个只有单一后端应用的简单仓库，而是一个保留历史基础并承载正式交付主线的复合型后端仓库。

## 当前正式交付口径

当前正式交付主线如下：
- 前端正式仓库：`https://github.com/X-1437/timeswise`（分支：`v2`）
- 后端正式目录：`mcp/src`
- 原有业务基础目录：`app`
- 全周期交付文档目录：`docs/first_week` 至 `docs/fifth_week`
- 正式交付说明目录：`docs/delivery`

## 目录说明

### 1. `app/`

原有 Web 形态后端基础代码。

该目录保留了传统项目制分析产品的后端实现，包括：
- 用户认证
- 项目管理
- 数据上传
- EDA
- 预处理
- 特征工程
- 预测
- 报告

说明：
- `app/` 是历史业务基础与复用来源
- 它不作为本次正式交付的主运行目录

### 2. `mcp/src/`

当前正式交付的对话式 MCP 后端目录。

该目录对应前端 `timeswise` 当前实际对接的后端主线，负责：
- 会话管理
- 对话驱动分析
- 文件上传与结果输出
- 调用 MCP 工具链完成 EDA、预处理、特征、预测和导出

说明：
- `mcp/src` 是当前正式交付的后端主目录
- 本次交付、部署接手和演示均以该目录为准

### 3. `mcp/first_week` 至 `mcp/fifth_week`

阶段性代码镜像与周度研发沉淀目录。

说明：
- 这些目录用于保留项目从第一周到第五周的过程资产
- 它们属于历史基线和演进证据，不替代 `mcp/src`

### 4. `docs/`

文档目录，分为两类：
- `docs/first_week` 至 `docs/fifth_week`：全周期周文档
- `docs/delivery`：最终交付与接手材料

## 本地启动

### 正式后端启动目录

```bash
cd mcp/src
```

### 安装依赖

```bash
pip install -r requirements.txt
```

### 环境变量

参考：
- `mcp/src/.env.example`

至少需要确认以下配置：
- `MONGODB_URI`
- `MONGODB_DB_NAME`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `OPENAI_MODEL`

### 启动后端

```bash
python backend.py
```

或：

```bash
uvicorn backend:app --host 0.0.0.0 --port 8000
```

默认访问地址：
- `http://localhost:8000`

接口文档：
- `http://localhost:8000/docs`

## 交付文档

如需查看完整交付材料，建议优先查看：
- `docs/delivery/9-1_项目交付汇报摘要.md`
- `docs/delivery/9_项目整体回顾与交付说明.md`
- `docs/delivery/9-2_项目最终交付清单.md`
- `docs/delivery/9-3_部署接手说明.md`
- `docs/delivery/9-4_最终交付结果汇总.md`

## 当前状态

当前项目状态定义为：
- 正式交付完成
- 进入部署接收阶段

需要特别区分：
- 正式交付完成：已完成
- 目标环境上线完成：待接收方部署与确认
