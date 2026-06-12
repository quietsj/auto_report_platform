from typing import Dict, Any
from .base_agent import BaseAgent


class ReportBuilderAgent(BaseAgent):
    def __init__(self, model: str = "deepseek-v4-flash"):
        super().__init__(model)
    
    async def run(self, data: Dict, intent: str) -> Dict[str, Any]:
        prompt = f"基于以下数据和分析意图，推荐合适的图表类型并生成报表配置：\n意图：{intent}\n数据：{data}"
        
        messages = [
            {"role": "system", "content": "你是一个报表构建专家。"},
            {"role": "user", "content": prompt}
        ]
        
        result = await self.llm_client.chat_completion(
            model=self.model,
            messages=messages,
            temperature=0.5
        )
        
        if not result["success"]:
            return {
                "success": False,
                "error": result["error"]
            }
        
        return {
            "success": True,
            "config": result["content"],
            "model": result["model"]
        }
