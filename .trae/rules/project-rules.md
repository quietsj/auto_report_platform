# AI Auto-ETL 平台开发规则

## 技术栈
- 前端: React 18 + TypeScript + Ant Design + AntV G2Plot/S2
- 后端: FastAPI + Python 3.10+
- 模型网关: LiteLLM (本地部署)
- 嵌入模型: BGE (本地 sentence-transformers)
- 数据基础设施: 阿里云 DataWorks + MaxCompute + ClickHouse

## 代码规范
1. Python: 使用 PEP 8，类型注解必须，docstring 使用 Google 风格
2. TypeScript: 严格模式，接口命名 I 前缀，类型优先
3. 错误处理: 统一使用 try/except + 自定义异常类
4. 日志: 使用 structlog，禁止 print
5. 配置: 环境变量 &gt; 配置文件 &gt; 默认值

## Agent 开发规范
1. 每个 Agent 必须是独立模块，继承 BaseAgent
2. Agent 间通信通过 LangGraph 状态机
3. LLM 调用统一走 litellm_client，禁止直接调用 API
4. Prompt 必须版本化，存储在 prompts/ 目录
5. 每次 LLM 调用必须记录到 Langfuse

## 数据库规范
1. SQL 生成目标: MaxCompute (离线) + ClickHouse (实时)
2. 表命名: 分层前缀 (ods_/dwd_/dws_/ads_)
3. 字段注释: 必须中文，枚举值必须说明
4. 分区字段: 必须 dt (yyyy-mm-dd)

## API 设计
1. RESTful 风格，路径使用 kebab-case
2. 响应统一格式: {code, data, message, trace_id}
3. 分页: page + size，最大 1000
4. 认证: JWT Bearer Token

## 前端规范
1. 组件: 函数组件 + Hooks，禁止 Class 组件
2. 状态: Zustand 全局，React Query 服务端
3. 图表: AntV G2Plot，主题跟随系统
4. 表格: AntV S2，支持透视分析