from typing import Dict, Any
from .base_agent import BaseAgent
from ..prompts.prompt_templates import INTENT_PARSER_PROMPT


class IntentParserAgent(BaseAgent):
    def __init__(self, model: str = "deepseek-chat"):
        super().__init__(model)
    
    async def run(self, query: str, schema_context: str = "") -> Dict[str, Any]:
        prompt = INTENT_PARSER_PROMPT.format(
            query=query,
            schema_context=schema_context
        )
        
        messages = [
            {"role": "system", "content": "你是一个专业的数据分析师助手，负责解析用户的自然语言查询。"},
            {"role": "user", "content": prompt}
        ]
        
        result = await self.litellm_client.chat_completion(
            model=self.model,
            messages=messages,
            temperature=0.3
        )
        
        if not result["success"]:
            return {
                "success": False,
                "error": result["error"]
            }
        
        return {
            "success": True,
            "intent": result["content"],
            "model": result["model"]
        }
