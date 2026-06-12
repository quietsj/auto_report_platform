from abc import ABC, abstractmethod
from typing import Dict, Any
from ..core.langchain_llm import llm_client


class BaseAgent(ABC):
    def __init__(self, model: str = "deepseek-chat"):
        self.model = model
        self.llm_client = llm_client

    @abstractmethod
    async def run(self, **kwargs) -> Dict[str, Any]:
        pass
