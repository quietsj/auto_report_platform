import os
from typing import Union, List

os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

app = FastAPI()
model = SentenceTransformer('BAAI/bge-large-zh-v1.5')


class EmbeddingRequest(BaseModel):
    model: str
    input: Union[str, List[str]]


class EmbeddingResponse(BaseModel):
    object: str = "list"
    data: list
    model: str
    usage: dict


@app.post("/v1/embeddings")
async def create_embedding(request: EmbeddingRequest):
    texts = [request.input] if isinstance(request.input, str) else request.input

    # BGE 模型需要在文本前加指令前缀（用于检索场景）
    instruction = "为这个句子生成表示以用于检索相关文章："
    texts = [instruction + t for t in texts]

    embeddings = model.encode(texts, normalize_embeddings=True)

    data = [
        {
            "object": "embedding",
            "index": i,
            "embedding": emb.tolist()
        }
        for i, emb in enumerate(embeddings)
    ]

    return EmbeddingResponse(
        data=data,
        model=request.model,
        usage={
            "prompt_tokens": sum(len(t) for t in texts),
            "total_tokens": sum(len(t) for t in texts)
        }
    )


@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [{"id": "bge-large-zh", "object": "model"}]
    }


if __name__ == "__main__":
    import uvicorn

    # chroma run --path ./chroma_data --port 8033 --host 0.0.0.0
    uvicorn.run(app, host="0.0.0.0", port=8001)