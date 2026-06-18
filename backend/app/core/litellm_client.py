from openai import AsyncOpenAI
from typing import List, Dict, Any, Type, Optional
from pydantic import BaseModel, Field
from .config import settings


class LiteLLMClient:
    def __init__(self):
        self.api_base = settings.LITELLM_API_BASE
        if not self.api_base.endswith("/v1"):
            self.api_base = self.api_base.rstrip("/") + "/v1"
        self.api_key = settings.LITELLM_MASTER_KEY
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.api_base,
            timeout=600.0,  # 10 分钟，避免 AI 生成长链路超时
            max_retries=2,
        )
    
    async def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> Dict[str, Any]:
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            return {
                "success": True,
                "content": response.choices[0].message.content,
                "model": model
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def completion(
        self,
        model: str,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> Dict[str, Any]:
        messages = [{"role": "user", "content": prompt}]
        return await self.chat_completion(model, messages, temperature, max_tokens, **kwargs)

    async def with_structured_output(
        self,
        model: str,
        messages: List[Dict[str, str]],
        response_format: Type[BaseModel],
        temperature: float = 0.7,
        max_tokens: int = 8000,
    ) -> Dict[str, Any]:
        """
        使用 OpenAI structured output 功能，确保模型返回符合 schema 的 JSON。

        Args:
            model: 模型名称
            messages: 对话消息列表
            response_format: Pydantic 模型类，定义输出结构
            temperature: 温度参数
            max_tokens: 最大 token 数

        Returns:
            包含 success、data（或 error）的字典
        """
        try:
            response = await self.client.beta.chat.completions.parse(
                model=model,
                messages=messages,
                response_format=response_format,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            parsed = response.choices[0].message.parsed
            if parsed is None:
                return {
                    "success": False,
                    "error": "模型未返回解析结果"
                }
            return {
                "success": True,
                "data": parsed.model_dump() if hasattr(parsed, 'model_dump') else parsed.dict(),
                "model": model
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


litellm_client = LiteLLMClient()
