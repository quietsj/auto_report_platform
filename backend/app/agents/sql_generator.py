from typing import Dict, Any
from .base_agent import BaseAgent
from ..prompts.prompt_templates import SQL_GENERATOR_PROMPT


class SQLGeneratorAgent(BaseAgent):
    def __init__(self, model: str = "deepseek-chat"):
        super().__init__(model)
    
    async def run(self, intent: str, schema_info: str) -> Dict[str, Any]:
        prompt = SQL_GENERATOR_PROMPT.format(
            intent=intent,
            schema_info=schema_info
        )
        
        messages = [
            {"role": "system", "content": "你是一个专业的 SQL 工程师，负责生成高质量的 MaxCompute SQL。"},
            {"role": "user", "content": prompt}
        ]
        
        result = await self.llm_client.chat_completion(
            model=self.model,
            messages=messages,
            temperature=0.2
        )
        
        if not result["success"]:
            return {
                "success": False,
                "error": result["error"]
            }
        
        return {
            "success": True,
            "sql": result["content"],
            "model": result["model"]
        }
