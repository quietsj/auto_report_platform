import httpx
from typing import List
from .config import settings


class EmbeddingService:
    def __init__(self):
        self.base_url = settings.EMBEDDING_SERVICE_URL
        self.instruction_prefix = "为这个句子生成表示以用于检索相关文章："
        self.model = "bge-large-zh"
    
    async def embed(self, text: str) -> List[float]:
        try:
            input_text = self.instruction_prefix + text
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/embeddings",
                    json={
                        "input": input_text,
                        "model": self.model
                    }
                )
                response.raise_for_status()
                result = response.json()
                return result["data"][0]["embedding"]
        except Exception as e:
            raise Exception(f"Embedding failed: {str(e)}")
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        try:
            input_texts = [self.instruction_prefix + text for text in texts]
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/embeddings",
                    json={
                        "input": input_texts,
                        "model": self.model
                    }
                )
                response.raise_for_status()
                result = response.json()
                return [item["embedding"] for item in result["data"]]
        except Exception as e:
            raise Exception(f"Batch embedding failed: {str(e)}")


embedding_service = EmbeddingService()
