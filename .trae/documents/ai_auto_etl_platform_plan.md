# AI Auto-ETL 智能报表平台开发计划

## 一、项目概述

基于需求文档，构建一个 AI 驱动的 Auto-ETL 平台，让业务人员通过自然语言描述分析需求，系统自动完成 ETL 链路开发、数据质量校验、报表生成并上线。

## 二、现有项目结构分析

### 2.1 当前文件
- `AI Auto-ETL 智能报表平台需求文档 .md` - 完整需求文档
- `目录树.md` - 推荐目录结构
- `项目架构.md` - 技术架构说明
- `config.yaml` - LiteLLM 配置
- `.env.example` - 环境变量模板
- `requirements.txt` - 基础依赖
- `servers/embedding_server.py` - 本地嵌入服务

### 2.2 缺少内容
- 完整的后端项目结构 (FastAPI)
- 前端项目结构 (React + TypeScript)
- 核心 Agent 模块
- API 路由
- 数据服务集成

## 三、开发阶段规划

### 阶段 1: 项目基础架构搭建 (MVP)

#### 1.1 目录结构创建
- 创建完整的前端/后端目录
- 配置文件初始化
- Docker 配置

#### 1.2 后端核心模块
- FastAPI 应用初始化
- 核心配置模块
- LiteLLM 客户端封装
- 嵌入服务集成
- Schema RAG 基础实现

#### 1.3 前端基础
- React + TypeScript + Vite 项目初始化
- Ant Design 组件库集成
- 基础布局组件

### 阶段 2: 核心功能开发 (MVP)

#### 2.1 智能输入模块
- 文本输入界面
- 意图解析 Agent
- 结构化意图展示
- 意图确认交互

#### 2.2 Auto-ETL 模块
- Schema RAG 检索
- SQL 生成 Agent
- SQL 语法校验
- 基础数据查询

#### 2.3 智能报表模块
- 基础图表展示 (AntV G2Plot)
- 数据表格 (AntV S2)
- 图表自动推荐

### 阶段 3: 数据平台集成 (V1.0)

#### 3.1 DataWorks 集成
- DataWorks OpenAPI 封装
- 节点创建
- 工作流创建
- 调度配置

#### 3.2 ClickHouse 集成
- 查询服务封装
- 物化视图管理
- 数据导入导出

#### 3.3 血缘与质量
- 血缘推导
- 质量规则自动生成
- 数据验证

### 阶段 4: 高级功能 (V1.5+)

#### 4.1 多轮对话
- 对话记忆
- 需求澄清
- 交互式修改

#### 4.2 图片识别
- 图片上传
- OCR + Vision 模型
- 意图解析

#### 4.3 订阅与分享
- 定时订阅
- 报表导出
- 分享链接

## 四、详细开发步骤

### Step 1: 创建完整目录结构
按照 `目录树.md` 的建议创建所有必要的目录和文件。

### Step 2: 后端开发
1. 配置 FastAPI 应用
2. 实现核心配置模块
3. 开发 LiteLLM 客户端
4. 实现嵌入服务集成
5. 开发 Agent 模块
6. 实现 API 路由

### Step 3: 前端开发
1. 初始化 React 项目
2. 配置 Ant Design 组件
3. 开发页面组件
4. 实现 API 调用
5. 集成 AntV 图表库

### Step 4: 集成测试
1. 端到端测试
2. 性能测试
3. 部署验证

## 五、文件清单

### 需要创建的文件

#### 后端
```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── litellm_client.py
│   │   └── embedding_service.py
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base_agent.py
│   │   ├── intent_parser.py
│   │   ├── sql_generator.py
│   │   ├── quality_checker.py
│   │   └── report_builder.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── schema_rag.py
│   │   ├── dataworks_service.py
│   │   └── clickhouse_service.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── etl.py
│   │   ├── query.py
│   │   ├── report.py
│   │   └── schema.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py
│   └── prompts/
│       └── prompt_templates.py
├── requirements.txt
└── Dockerfile
```

#### 前端
```
frontend/
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── components/
│   │   ├── charts/
│   │   │   ├── LineChart.tsx
│   │   │   ├── BarChart.tsx
│   │   │   └── PieChart.tsx
│   │   ├── filters/
│   │   └── layout/
│   ├── pages/
│   │   ├── Dashboard.tsx
│   │   ├── Editor.tsx
│   │   └── Settings.tsx
│   ├── services/
│   │   ├── api.ts
│   │   ├── embedding.ts
│   │   └── litellm.ts
│   ├── stores/
│   │   └── useStore.ts
│   ├── utils/
│   └── types/
├── package.json
├── vite.config.ts
└── tsconfig.json
```

#### 配置和脚本
```
config/
├── litellm-config.yaml
├── dataworks-config.yaml
└── clickhouse-config.yaml

scripts/
├── start-all.ps1
├── start-all.sh
└── setup.ps1

docker-compose.yml
```

## 六、技术实现要点

### 6.1 代码规范
- Python: PEP 8, 类型注解, Google 风格 docstring
- TypeScript: 严格模式, 接口命名 I 前缀
- 错误处理: 统一异常类
- 日志: structlog

### 6.2 Agent 开发规范
- 每个 Agent 继承 BaseAgent
- 使用 LangGraph 编排
- LLM 调用通过 litellm_client
- Prompt 版本化管理

### 6.3 数据安全
- 敏感字段脱敏
- 权限控制
- 审计日志
- SQL 注入防护

## 七、验收标准

### MVP
- ✅ 文本输入 → 意图解析
- ✅ SQL 生成 → 基础报表展示
- ✅ 端到端流程跑通

### V1.0
- ✅ DataWorks 集成
- ✅ 血缘推导
- ✅ 质量校验
- ✅ 自动创建节点并调度

### V1.5+
- ✅ 图片识别准确率 ≥ 80%
- ✅ 多轮对话
- ✅ 订阅推送
- ✅ 业务自助使用率 ≥ 60%

## 八、风险与应对

| 风险 | 应对 |
|------|------|
| DeepSeek API 不稳定 | LiteLLM fallback 到百炼 |
| Text-to-SQL 准确率不足 | 人工确认 + 质量校验 |
| DataWorks OpenAPI 限流 | 队列 + 重试 + 异步 |
| 用户意图理解偏差 | 多轮对话澄清 + 预览确认 |
