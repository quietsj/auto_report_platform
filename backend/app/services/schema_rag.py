import chromadb
from typing import List, Dict, Any
from ..core.config import settings
from ..core.embedding_service import embedding_service


class SchemaRAGService:
    def __init__(self):
        self.client = chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
        self.collection = self.client.get_or_create_collection("table_schemas")
    
    async def add_schema(self, table_name: str, schema_info: str, metadata: Dict = None):
        embedding = await embedding_service.embed(schema_info)
        self.collection.add(
            documents=[schema_info],
            embeddings=[embedding],
            metadatas=[metadata or {}],
            ids=[table_name]
        )
    
    async def search_schemas(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        query_embedding = await embedding_service.embed(query)
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k
        )
        
        schemas = []
        for i in range(len(results["ids"][0])):
            schemas.append({
                "table_name": results["ids"][0][i],
                "schema_info": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i]
            })
        return schemas
    
    def list_tables(self) -> List[str]:
        return self.collection.get()["ids"]


schema_rag_service = SchemaRAGService()
