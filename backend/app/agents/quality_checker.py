from typing import Dict, Any
from .base_agent import BaseAgent


class QualityCheckerAgent(BaseAgent):
    def __init__(self, model: str = "deepseek-chat"):
        super().__init__(model)
    
    async def run(self, sql: str) -> Dict[str, Any]:
        prompt = f"请检查以下 SQL 的质量，包括语法正确性、性能优化建议和潜在问题：\n\n{sql}"
        
        messages = [
            {"role": "system", "content": "你是一个 SQL 质量检查专家。"},
            {"role": "user", "content": prompt}
        ]
        
        result = await self.llm_client.chat_completion(
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
            "report": result["content"],
            "model": result["model"]
        }
