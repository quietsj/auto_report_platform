from abc import ABC, abstractmethod
from typing import Dict, Any
from ..core.litellm_client import litellm_client


class BaseAgent(ABC):
    def __init__(self, model: str = "deepseek-chat"):
        self.model = model
        self.litellm_client = litellm_client
    
    @abstractmethod
    async def run(self, **kwargs) -> Dict[str, Any]:
        pass
