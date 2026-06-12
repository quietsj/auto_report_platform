import httpx
from typing import List
from .config import settings


class EmbeddingService:
    def __init__(self):
        self.base_url = settings.EMBEDDING_SERVICE_URL
        self.instruction_prefix = "为这个句子生成表示以用于检索相关文章："
        self.model = "bge-large-zh"
        # 单次批量请求最大条数，避免一次性提交过多导致 embedding 服务超时
        self.batch_size = 16

    async def embed(self, text: str) -> List[float]:
        try:
            input_text = self.instruction_prefix + text
            async with httpx.AsyncClient(timeout=300.0) as client:
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
        """
        批量获取嵌入向量

        内部按 self.batch_size 自动切分子批次，避免一次性请求过多导致 embedding 服务超时
        """
        if not texts:
            return []

        all_embeddings: List[List[float]] = []
        # 按 batch_size 切分子批次
        for start in range(0, len(texts), self.batch_size):
            sub_batch = texts[start:start + self.batch_size]
            input_texts = [self.instruction_prefix + t for t in sub_batch]
            try:
                async with httpx.AsyncClient(timeout=300.0) as client:
                    response = await client.post(
                        f"{self.base_url}/v1/embeddings",
                        json={
                            "input": input_texts,
                            "model": self.model
                        }
                    )
                    response.raise_for_status()
                    result = response.json()
                    sub_embeddings = [item["embedding"] for item in result["data"]]
                    all_embeddings.extend(sub_embeddings)
                    print(
                        f"[Embedding] 子批次 {start // self.batch_size + 1} 完成: "
                        f"{len(sub_batch)} 条，累计 {len(all_embeddings)}/{len(texts)}"
                    )
            except httpx.ReadTimeout:
                raise Exception(
                    f"Batch embedding 超时: 当前子批次 {len(sub_batch)} 条，"
                    f"已处理 {start}/{len(texts)} 条"
                )
            except Exception as e:
                raise Exception(
                    f"Batch embedding failed (子批次 {start // self.batch_size + 1}): {str(e)}"
                )

        return all_embeddings


embedding_service = EmbeddingService()
