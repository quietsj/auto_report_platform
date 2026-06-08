# AI Auto-ETL 平台 - 基于 Demo 代码更新模块 - 实现计划

## [x] Task 1: 更新 LiteLLM 客户端
- **Priority**: P0
- **Depends On**: None
- **Description**: 
  - 修改 `backend/app/core/litellm_client.py`
  - 使用 OpenAI SDK 替代直接的 litellm 库调用
  - 参考 `demo/demo_litellm.py` 的实现
  - 保持现有接口不变
- **Acceptance Criteria Addressed**: AC-1
- **Test Requirements**:
  - `programmatic` TR-1.1: 可以成功获取模型列表
  - `programmatic` TR-1.2: chat completion 调用成功并返回响应
  - `human-judgement` TR-1.3: 错误处理和日志输出合理
- **Notes**: 确保向后兼容，现有 Agent 不需要修改代码

## [x] Task 2: 更新 Embedding 服务集成
- **Priority**: P0
- **Depends On**: None
- **Description**: 
  - 修改 `backend/app/core/embedding_service.py`
  - 使用标准的 OpenAI 兼容 API 格式
  - 添加 BGE 指令前缀
  - 支持单文本和批量文本
  - 参考 `demo/demo_embedding_direct.py`
- **Acceptance Criteria Addressed**: AC-2
- **Test Requirements**:
  - `programmatic` TR-2.1: 单文本嵌入成功，维度正确
  - `programmatic` TR-2.2: 批量嵌入成功
  - `programmatic` TR-2.3: BGE 指令前缀正确添加
  - `programmatic` TR-2.4: 向量是归一化的

## [x] Task 3: 更新 Schema RAG 服务
- **Priority**: P0
- **Depends On**: Task 2
- **Description**: 
  - 修改 `backend/app/services/schema_rag.py`
  - 使用 ChromaDB HTTP 客户端替代 PersistentClient
  - 先获取嵌入向量再与 ChromaDB 交互
  - 参考 `demo/demo_vector_db.py`
- **Acceptance Criteria Addressed**: AC-3, AC-4
- **Test Requirements**:
  - `programmatic` TR-3.1: 可以创建和获取集合
  - `programmatic` TR-3.2: 添加文档和向量成功
  - `programmatic` TR-3.3: 查询文档成功，返回相关结果
  - `human-judgement` TR-3.4: 代码结构清晰

## [x] Task 4: 更新配置文件和依赖
- **Priority**: P1
- **Depends On**: None
- **Description**: 
  - 更新 `backend/requirements.txt`
  - 确保所有依赖正确列出
  - 更新配置文件中的默认端口设置
- **Acceptance Criteria Addressed**: AC-1, AC-2, AC-3
- **Test Requirements**:
  - `programmatic` TR-4.1: pip install 成功完成
  - `human-judgement` TR-4.2: 配置项合理
