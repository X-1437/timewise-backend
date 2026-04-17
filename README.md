# Timewise 后端 API

基于 FastAPI + MongoDB 的时序数据分析系统后端服务。

## 技术栈

- **框架**: FastAPI
- **数据库**: MongoDB (时序集合)
- **数据处理**: pandas, numpy, scipy
- **认证**: JWT

## 功能模块

1. **用户认证** - 注册、登录、JWT令牌
2. **项目管理** - 创建、读取、更新、删除项目
3. **数据接入** - CSV/Excel文件上传与存储
4. **EDA** - 探索性数据分析（缺失值、异常值、统计量）
5. **预处理** - 重采样、缺失值填充、异常值处理、噪声过滤
6. **特征工程**
   - 时域特征：趋势、季节性、自相关、滞后、滚动统计、差分
   - 频域特征：FFT、小波变换、PSD、频谱图
7. **预测** - 时间序列预测

## 环境要求

- Python 3.8+
- MongoDB 5.0+ (建议使用MongoDB Atlas或本地安装)

## 本地运行

### 1. 克隆项目

```bash
git clone https://github.com/X-1437/timewise-backend.git
cd timewise-backend
```

### 2. 创建虚拟环境

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

创建 `.env` 文件：

```env
MONGO_URI=mongodb://localhost:27017
DATABASE_NAME=timewise
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### 5. 启动MongoDB

本地启动MongoDB服务，或使用MongoDB Atlas云端数据库。

### 6. 启动服务

```bash
uvicorn app.main:app --reload
```

服务将在 http://localhost:8000 启动。

API文档: http://localhost:8000/docs

## API 接口

| 模块 | 路径 | 说明 |
|------|------|------|
| 认证 | `/api/v1/auth/register` | 用户注册 |
| 认证 | `/api/v1/auth/login` | 用户登录 |
| 项目 | `/api/v1/projects` | CRUD项目 |
| 数据 | `/api/v1/projects/{id}/data` | 上传数据文件 |
| EDA | `/api/v1/projects/{id}/eda` | 探索性数据分析 |
| 预处理 | `/api/v1/projects/{id}/preprocess` | 数据预处理 |
| 特征 | `/api/v1/projects/{id}/features` | 特征提取 |
| 预测 | `/api/v1/projects/{id}/forecast` | 时间序列预测 |

## MongoDB 时序集合

项目使用MongoDB时序集合存储处理后的时序数据：

- 集合名称: `time_series_data`
- 索引: 自动创建 `metadata.project_id` 和 `timestamp` 复合索引

## 目录结构

```
timewise-backend/
├── app/
│   ├── core/           # 核心配置（安全、依赖）
│   ├── models/         # 数据模型
│   ├── routers/        # API路由
│   ├── schemas/        # Pydantic模型
│   ├── utils/          # 工具函数
│   ├── config.py       # 配置文件
│   ├── database.py     # 数据库连接
│   └── main.py         # 应用入口
├── uploads/            # 上传文件目录
├── .env                # 环境变量
├── requirements.txt    # 依赖列表
└── run_server.py       # 服务启动脚本
```

## 许可证

MIT License