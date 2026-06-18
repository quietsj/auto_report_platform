"""数仓链路生成 Agent - 使用 LCEL + RunnableWithMessageHistory 实现多轮会话"""
from __future__ import annotations

import json
import re
from typing import Dict, Any, Optional
from .base_agent import BaseAgent
from ..prompts.pipeline_prompt import PipelineResult, SYSTEM_RULES, get_schema_for_prompt
from ..services.knowledge_rag import knowledge_rag_service
from ..core.session_manager import SessionManager


class PipelineAgent(BaseAgent):
    """数仓链路生成 Agent

    核心能力:
    1. 结构化输出（JSON 格式，包含 DWD/DWS/ADS 分层设计
    2. RAG 知识增强（从知识库检索相关表定义）
    3. 多轮会话（使用 RunnableWithMessageHistory + SummaryBufferChatHistory）
    """

    def __init__(self, model: str = "deepseek-v4-flash", session_id: Optional[str] = None):
        super().__init__(model)
        self.session_id = session_id

    # ---------- RAG 知识增强 ----------

    async def _retrieve_knowledge(self, user_input: str, top_k: int = 5) -> str:
        """从知识库检索相关内容，返回格式化的上下文字符串"""
        try:
            docs = await knowledge_rag_service.search(query=user_input, top_k=top_k)
            if not docs:
                return "（未检索到相关知识库内容）"

            parts = []
            for idx, doc in enumerate(docs, 1):
                content = doc.get("content", "")
                meta = doc.get("metadata") or {}
                source = ""
                if isinstance(meta, dict):
                    source = meta.get("source_name") or meta.get("source") or ""
                if source:
                    parts.append(f"【参考 {idx} - {source}】\n{content}")
                else:
                    parts.append(f"【参考 {idx}】\n{content}")
            return "\n\n".join(parts)
        except Exception as e:
            print(f"[PipelineAgent] RAG 检索异常: {e}")
            return "（RAG 检索异常，跳过知识库内容）"

    # ---------- 业务校验 ----------

    def _validate_output(self, data: Dict[str, Any]) -> tuple[bool, str]:
        """校验输出数据结构是否完整"""
        tables = data.get("tables")
        if not tables or not isinstance(tables, list) or len(tables) == 0:
            return False, "tables 列表为空或不存在"

        valid_layers = {"dwd", "dim", "dws", "ads"}
        for table in tables:
            layer = table.get("layer")
            if layer not in valid_layers:
                return False, f"无效的层级: {layer}，有效值: dwd/dim/dws/ads"
            if not table.get("table_name") or not table.get("ddl_sql"):
                return False, f"表结构不完整: {table.get('table_name')}"
            if not table.get("insert_sql"):
                return False, f"缺少 insert_sql: {table.get('table_name')}"

        return True, "OK"

    # ---------- JSON 解析 ----------

    def _parse_json_output(self, content: str) -> Optional[Dict[str, Any]]:
        """从模型输出中解析 JSON 对象"""
        data = None

        # 策略 1：直接解析
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

        # 策略 2：提取 ```json ... ``` 代码块
        match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1).strip())
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass

        # 策略 3：提取最外层的 {...}
        match = re.search(r'\{[\s\S]*\}', content)
        if match:
            try:
                data = json.loads(match.group(0))
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass

        return None

    # ---------- 主流程 ----------

    async def run(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None,
        session_manager: Optional[SessionManager] = None,
    ) -> Dict[str, Any]:
        """生成数仓链路

        通过 session_manager 管理多轮会话历史。

        Args:
            user_input: 用户需求描述
            context: 可选的额外上下文（当前未使用）
            session_manager: 会话管理器，用于获取/保存 LLM 历史

        Returns:
            包含 success / data 或 error 的字典
        """
        try:
            # Step 1: RAG 检索
            rag_context = await self._retrieve_knowledge(user_input, top_k=5)

            # Step 2: 构建用户输入（包含 RAG 上下文）
            full_user_input = f"## 知识库参考内容\n{rag_context}\n\n## 当前需求\n{user_input}"

            # Step 3: 调用 LLM（使用 LCEL + RunnableWithMessageHistory）
            # 构造 get_session_history 回调（供 chat_with_history 内部使用）
            def _get_history():
                if session_manager is not None:
                    llm_history = session_manager.get_llm_history(self.session_id)
                    if llm_history is not None:
                        llm_history.messages = llm_history.messages[-6:]
                        return llm_history
                raise ValueError("llm_history 未初始化")

            # 调用 LLM（传入 get_schema_for_prompt 已处理 `{{}} 转义）
            result = await self.llm_client.chat_with_history(
                model=self.model,
                user_input=full_user_input,
                get_session_history=_get_history,
                system_message=SYSTEM_RULES + get_schema_for_prompt(PipelineResult),
                temperature=0.7,
                max_tokens=30000,
            )

            if not result.get("success"):
                error = result.get("error", "未知错误")
                print(f"[PipelineAgent] LLM 调用失败: {error}")
                return {
                    "success": False,
                    "error": error,
                    "session_id": self.session_id,
                }

            content = result.get("content", "")

            # Step 4: 解析 JSON 输出
            data = self._parse_json_output(content)

            if not data:
                return {
                    "success": False,
                    "error": "无法解析模型输出为 JSON 格式",
                    "session_id": self.session_id,
                }

            # Step 5: 业务校验
            is_valid, msg = self._validate_output(data)
            if not is_valid:
                print(f"[PipelineAgent] 业务校验失败: {msg}")
                return {
                    "success": False,
                    "error": f"输出结构校验失败: {msg}",
                    "session_id": self.session_id,
                }

            print(f"[PipelineAgent] 生成成功，tables={len(data.get('tables', []))}")

            return {
                "success": True,
                "session_id": self.session_id,
                "rag_context_used": rag_context,
                **data,
            }

        except Exception as e:
            print(f"[PipelineAgent] 异常: {e}")
            return {
                "success": False,
                "error": str(e),
                "session_id": self.session_id,
            }
