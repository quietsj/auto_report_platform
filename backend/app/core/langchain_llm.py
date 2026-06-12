"""LangChain 版 LLM 客户端，通过 ChatLiteLLM 调用 litellm 模型网关"""
from __future__ import annotations

from typing import List, Dict, Any, Optional
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from .config import settings


class LangChainLLMClient:
    """基于 LangChain 的 LLM 客户端（通过 ChatOpenAI 以 OpenAI 兼容协议指向本地 litellm 网关）"""

    def __init__(self):
        self.api_base = settings.LITELLM_API_BASE
        self.api_key = settings.LITELLM_MASTER_KEY
        self.model_list = settings.LITELLM_MODEL_LIST

    def _get_model_name(self, model: str) -> str:
        return model

    def create_chat_model(self, model: str, **kwargs) -> ChatOpenAI:
        """创建单个 ChatOpenAI 实例，通过 base_url 指向本地 litellm 网关"""
        full_model = self._get_model_name(model)
        # 调试日志：确认每次调用使用的 base_url 和 model，避免出现"配置正确但调用走错地方"
        print(f"[LangChainLLM] create_chat_model: model={model} -> full_model={full_model}, base_url={self.api_base}")
        return ChatOpenAI(
            model=full_model,
            api_key=self.api_key,
            base_url=self.api_base,
            timeout=600.0,  # 10 分钟，避免 AI 生成长链路超时
            max_retries=2,
            **kwargs,
        )

    async def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 20000,
        **kwargs
    ) -> Dict[str, Any]:
        """
        兼容旧接口：通过传入 messages 列表（dict）调用 LangChain，返回格式与旧接口一致。
        """
        try:
            chat_model = self.create_chat_model(
                model,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )

            # 转换为 LangChain 消息格式
            langchain_messages: List[BaseMessage] = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "system":
                    langchain_messages.append(SystemMessage(content=content))
                elif role == "user":
                    langchain_messages.append(HumanMessage(content=content))
                else:
                    # 其他 role 也当作 HumanMessage 处理
                    langchain_messages.append(HumanMessage(content=content))

            print(f"[LangChainLLM] 开始调用 litellm 网关: {self.api_base}, model={model}, messages={len(langchain_messages)} 条")
            response = chat_model.invoke(langchain_messages)
            content = response.content if hasattr(response, "content") else str(response)
            print(f"[LangChainLLM] 调用成功，返回内容长度: {len(content) if isinstance(content, str) else 'N/A'}")

            return {
                "success": True,
                "content": content,
                "model": model,
            }
        except Exception as e:
            print(f"[LangChainLLM] 调用 litellm 网关失败: base_url={self.api_base}, model={model}, error={e}")
            return {
                "success": False,
                "error": str(e),
            }


llm_client = LangChainLLMClient()
