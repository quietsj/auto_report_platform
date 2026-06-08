from openai import AsyncOpenAI
from typing import List, Dict, Any
from .config import settings


class LiteLLMClient:
    def __init__(self):
        self.api_base = settings.LITELLM_API_BASE
        if not self.api_base.endswith("/v1"):
            self.api_base = self.api_base.rstrip("/") + "/v1"
        self.api_key = settings.LITELLM_MASTER_KEY
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.api_base
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


litellm_client = LiteLLMClient()
