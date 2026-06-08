# AI Auto-ETL 平台 - 基于 Demo 代码更新模块

## Overview
- **Summary**: 根据 demo 目录下的示例代码，更新和完善 AI Auto-ETL 平台的核心模块，包括 LiteLLM 客户端、嵌入服务集成和向量数据库（ChromaDB）的使用。
- **Purpose**: 确保平台能够正确地与 LiteLLM 网关、本地 Embedding 服务和 ChromaDB 协同工作，参考 demo 中的最佳实践。
- **Target Users**: 开发人员和系统管理员

## Goals
- 更新 LiteLLM 客户端实现，使用 OpenAI SDK 风格的调用方式
- 完善嵌入服务集成，正确调用本地 `/v1/embeddings` API
- 更新 Schema RAG 服务，使用 ChromaDB HTTP 客户端
- 确保所有模块能够正常协同工作

## Non-Goals (Out of Scope)
- 不修改前端代码
- 不重构现有 Agent 逻辑（除必要的集成代码）
- 不添加新的功能特性

## Background & Context
项目已有完整的架构，但核心模块的实现与 demo 中的最佳实践存在差异：
1. `demo_litellm.py` 展示了如何正确使用 OpenAI SDK 连接 LiteLLM 网关
2. `demo_vector_db.py` 和 `demo_embedding_direct.py` 展示了正确的 ChromaDB 和 Embedding 服务集成方式
3. `servers/embedding_server.py` 提供了标准的 OpenAI 兼容的嵌入服务 API

## Functional Requirements
- **FR-1**: LiteLLM 客户端使用 OpenAI SDK 调用方式
- **FR-2**: 嵌入服务正确调用本地 `/v1/embeddings` API
- **FR-3**: Schema RAG 使用 ChromaDB HTTP 客户端
- **FR-4**: 支持批量嵌入和向量检索
- **FR-5**: 添加 BGE 模型的指令前缀

## Non-Functional Requirements
- **NFR-1**: 所有 API 调用超时设置合理（30秒）
- **NFR-2**: 错误处理完善，提供有用的调试信息
- **NFR-3**: 向量归一化处理

## Constraints
- **Technical**: 必须使用 OpenAI 兼容的 API 格式
- **Business**: 必须保持对现有代码的向后兼容性
- **Dependencies**: 依赖 `openai`, `chromadb`, `sentence-transformers` 等库

## Assumptions
- LiteLLM 网关运行在 `http://localhost:4000`
- Embedding 服务运行在 `http://localhost:8001`
- 可用的模型名称在配置中正确定义

## Acceptance Criteria

### AC-1: LiteLLM 客户端更新
- **Given**: 已配置好 LiteLLM 网关
- **When**: 调用 chat completion API
- **Then**: 使用 OpenAI SDK 成功获取模型响应
- **Verification**: `programmatic`

### AC-2: 嵌入服务集成更新
- **Given**: 本地嵌入服务正在运行
- **When**: 请求获取文本向量
- **Then**: 正确调用 `/v1/embeddings` 并返回归一化的向量
- **Verification**: `programmatic`
- **Notes**: 需添加 BGE 指令前缀 "为这个句子生成表示以用于检索相关文章："

### AC-3: ChromaDB 集成更新
- **Given**: ChromaDB 服务运行
- **When**: 添加或查询 Schema 文档
- **Then**: 使用 HTTP 客户端，先获取向量再与 ChromaDB 交互
- **Verification**: `programmatic`

### AC-4: 批量操作支持
- **Given**: 有多个文本需要处理
- **When**: 执行批量嵌入或批量添加到向量数据库
- **Then**: 操作成功完成，所有向量正确存储
- **Verification**: `programmatic`

## Open Questions
- [ ] 是否需要保留现有 ChromaDB PersistentClient 作为备选方案？
