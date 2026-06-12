"""数仓链路生成 Agent - LangChain + RAG（共享知识库 knowledge_base collection）"""
from __future__ import annotations

import json
import re
from typing import Dict, Any, Optional, Tuple, List
from .base_agent import BaseAgent
from ..prompts.pipeline_prompt import PIPELINE_SYSTEM_PROMPT, PIPELINE_USER_PROMPT
from ..services.knowledge_rag import knowledge_rag_service  # 共享知识库 service（collection: knowledge_base）


class PipelineAgent(BaseAgent):
    """根据用户需求 + RAG 知识库上下文，自动生成完整数仓链路"""

    def __init__(self, model: str = "deepseek-v4-flash"):
        super().__init__(model)

    async def _retrieve_rag_context(self, user_input: str, top_k: int = 5) -> str:
        """从共享知识库（knowledge_base collection）检索相关内容作为上下文

        与知识库页面共用同一个 knowledge_rag_service / collection，
        避免之前"两套 collection 数据脱节"的问题。
        """
        try:
            # 共享知识库 service：查询 knowledge_base collection（用户在知识库页面导入的内容）
            docs = await knowledge_rag_service.search(query=user_input, top_k=top_k)
            if not docs:
                return "（未从知识库检索到相关内容）"

            lines = ["## 知识库参考内容\n"]
            for idx, doc in enumerate(docs, 1):
                content = doc.get("content", "")
                source = ""
                meta = doc.get("metadata") or {}
                if isinstance(meta, dict):
                    source = meta.get("source_name") or meta.get("source") or meta.get("doc_id") or ""
                header = f"### [{idx}] 来源: {source}" if source else f"### [{idx}]"
                lines.append(header)
                lines.append(f"```\n{content}\n```")
                if meta and isinstance(meta, dict):
                    lines.append(f"元数据: {json.dumps(meta, ensure_ascii=False, default=str)}")
                lines.append("")
            return "\n".join(lines)
        except Exception as e:
            print(f"[PipelineAgent] RAG 检索异常（使用共享知识库）: {e}")
            return "（RAG 检索异常，跳过知识库内容）"

    def _parse_json_from_response(self, content: str) -> Optional[Dict[str, Any]]:
        """从模型返回内容中提取 JSON"""
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:] if lines[0].startswith("```") else lines)
            content = content.rsplit("```", 1)[0].strip()

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        match = re.search(r'\{[\s\S]*\}', content)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        return None

    def _validate_result(self, result: Dict[str, Any]) -> Tuple[bool, str]:
        """验证返回结构是否完整"""
        required_keys = ["demand_analysis", "tables", "clickhouse_tables", "sync_scripts", "execution_order"]
        for key in required_keys:
            if key not in result:
                return False, f"缺少必需字段: {key}"

        if not isinstance(result.get("tables"), list) or len(result["tables"]) == 0:
            return False, "tables 必须是非空数组"

        valid_layers = {"dwd", "dim", "dws", "ads"}
        for table in result["tables"]:
            layer = table.get("layer")
            if layer not in valid_layers:
                return False, f"无效的层级: {layer}，有效值: dwd/dim/dws/ads"

            if not table.get("table_name") or not table.get("ddl_sql"):
                return False, f"表结构不完整（缺少 table_name 或 ddl_sql）: {table.get('table_name')}"

            if not table.get("insert_sql"):
                return False, f"缺少 insert_sql（数据加工逻辑）: {table.get('table_name')}"

        return True, "OK"

    async def run(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None,
        max_retries: int = 2,
    ) -> Dict[str, Any]:
        """
        生成数仓链路（带 RAG 增强）

        Args:
            user_input: 用户需求描述
            context: 可选的业务上下文
            max_retries: 最大重试次数

        Returns:
            包含 demand_analysis / tables / clickhouse_tables / sync_scripts / execution_order 的字典
        """
        # Step 1: RAG 检索知识库上下文
        rag_context = await self._retrieve_rag_context(user_input, top_k=5)
        context_str = json.dumps(context, ensure_ascii=False) if context else "无"

        user_prompt = PIPELINE_USER_PROMPT.format(
            user_input=user_input,
            context=context_str,
            rag_context=rag_context,
            bizdate='{bizdate}'
        )

        messages = [
            {"role": "system", "content": PIPELINE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]

        for attempt in range(max_retries):
            print(f"[PipelineAgent] 调用模型，attempt={attempt + 1}")

            result = await self.llm_client.chat_completion(
                model=self.model,
                messages=messages,
                temperature=0.7
            )

            if not result.get("success"):
                print(f"[PipelineAgent] 模型调用失败: {result.get('error')}")
                continue

            content = result["content"]
            parsed = self._parse_json_from_response(content)

            if parsed is None:
                print(f"[PipelineAgent] 第 {attempt + 1} 次尝试：JSON 解析失败，追加提示重试")
                messages.append({"role": "assistant", "content": content})
                messages.append({
                    "role": "user",
                    "content": (
                        "你的上一次回答无法被解析为有效 JSON。"
                        "请重新按照 JSON schema 输出，**只输出 JSON**，不要任何解释文字或 Markdown 代码块。"
                    )
                })
                continue

            is_valid, msg = self._validate_result(parsed)
            if not is_valid:
                print(f"[PipelineAgent] 第 {attempt + 1} 次尝试：结构验证失败 - {msg}，追加提示重试")
                messages.append({"role": "assistant", "content": content})
                messages.append({
                    "role": "user",
                    "content": (
                        f"JSON 结构验证失败: {msg}。"
                        "请重新按 JSON schema 输出，**只输出 JSON**，不要任何解释文字。"
                    )
                })
                continue

            print(f"[PipelineAgent] 生成成功，tables={len(parsed.get('tables', []))}")
            return {
                "success": True,
                "rag_context_used": rag_context,
                **parsed
            }

        print("[PipelineAgent] 所有重试均失败")
        return {
            "success": False,
            "error": "模型未能生成符合规范的 JSON 结构，请尝试简化需求或稍后重试。",
            "attempted_times": max_retries
        }
