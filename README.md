# AI Auto-ETL 智能报表平台

一个基于 AI 的自动化 ETL 和报表生成平台，支持自然语言查询，自动解析意图，生成 SQL，创建 DataWorks 任务，并生成智能报表。

## 技术栈

### 后端
- Python 3.10+
- FastAPI
- LangChain / LangGraph
- LiteLLM (多模型网关)
- ChromaDB (向量数据库)
- DataWorks OpenAPI

### 前端
- React 18
- TypeScript
- Vite
- Ant Design
- AntV G2Plot / S2

## 项目结构

```
auto_report_generate/
├── backend/                 # 后端服务
│   ├── app/
│   │   ├── agents/         # Agent 模块
│   │   ├── core/           # 核心配置
│   │   ├── routers/        # API 路由
│   │   ├── services/       # 业务服务
│   │   └── models/         # 数据模型
│   └── requirements.txt
├── frontend/               # 前端应用
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   └── services/
│   └── package.json
├── servers/                # 辅助服务
│   └── embedding_server.py
├── config/                 # 配置文件
├── scripts/                # 启动脚本
└── docs/                   # 文档
```

## 快速开始

### 1. 环境准备

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，填入你的 API Keys
```

### 2. 启动依赖服务

```bash
# 使用 Docker Compose 启动 Redis 和 ChromaDB
docker-compose up -d
```

### 3. 启动后端服务

```bash
# Windows
scripts\start-all.ps1

# Linux/Mac
chmod +x scripts/start-all.sh
scripts/start-all.sh
```

### 4. 启动各个服务

打开多个终端窗口，分别执行：

```bash
# 终端 1: 启动 LiteLLM Proxy
litellm --config config.yaml --port 4000

# 终端 2: 启动 Embedding 服务
cd servers
python embedding_server.py

# 终端 3: 启动后端 API
cd backend
uvicorn app.main:app --reload --port 8000

# 终端 4: 启动前端
cd frontend
npm install
npm run dev
```

## 功能模块

### 1. 智能输入
- 自然语言查询解析
- 意图识别和结构化
- 多轮对话支持

### 2. Auto-ETL
- Schema RAG 检索
- 血缘推导
- SQL 自动生成
- DataWorks 任务自动创建

### 3. 数据质量
- 自动质量规则生成
- 异常检测和告警
- 质量报告

### 4. 智能报表
- 图表自动推荐
- 洞察自动生成
- 交互式仪表盘

## API 文档

启动后端服务后，访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 开发指南

### 后端开发

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 前端开发

```bash
cd frontend
npm install
npm run dev
```

## 许可证

MIT License
