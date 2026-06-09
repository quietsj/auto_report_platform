import chromadb
from typing import List, Dict, Any
from ..core.config import settings


class SchemaRAGService:
    def __init__(self):
        self.in_memory_schemas: Dict[str, Dict[str, Any]] = {}
        self.client = None
        self.collection = None
        self.embedding_enabled = False
        
        try:
            self.client = chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
            self.collection = self.client.get_or_create_collection("table_schemas")
            self.embedding_enabled = True
            
            try:
                data = self.collection.get()
                for i in range(len(data["ids"])):
                    self.in_memory_schemas[data["ids"][i]] = {
                        "schema_info": data["documents"][i],
                        "metadata": data["metadatas"][i]
                    }
            except Exception:
                pass
        except Exception as e:
            print(f"Warning: Could not connect to ChromaDB: {e}")
    
    async def add_schema(self, table_name: str, schema_info: str, metadata: Dict = None):
        self.in_memory_schemas[table_name] = {
            "schema_info": schema_info,
            "metadata": metadata or {}
        }
        
        if self.collection:
            try:
                from ..core.embedding_service import embedding_service
                
                existing = self.collection.get(ids=[table_name])
                if existing["ids"]:
                    self.collection.delete(ids=[table_name])
                
                embedding = await embedding_service.embed(schema_info)
                
                self.collection.add(
                    documents=[schema_info],
                    embeddings=[embedding],
                    metadatas=[metadata or {}],
                    ids=[table_name]
                )
                print(f"Schema '{table_name}' added to ChromaDB with embedding")
            except Exception as e:
                print(f"Warning: Could not save to ChromaDB: {e}")
    
    async def search_schemas(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        if self.collection and self.embedding_enabled:
            try:
                from ..core.embedding_service import embedding_service
                
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
            except Exception as e:
                print(f"Warning: Vector search failed, falling back to keyword search: {e}")
        
        results = []
        for table_name, data in self.in_memory_schemas.items():
            if query.lower() in table_name.lower() or query.lower() in data["schema_info"].lower():
                results.append({
                    "table_name": table_name,
                    "schema_info": data["schema_info"],
                    "metadata": data["metadata"],
                    "distance": 0.0
                })
        return results[:top_k]
    
    def list_tables(self) -> List[Dict[str, Any]]:
        return [
            {
                "table_name": table_name,
                "schema_info": data["schema_info"],
                "metadata": data["metadata"]
            }
            for table_name, data in self.in_memory_schemas.items()
        ]
    
    def delete_table(self, table_name: str) -> bool:
        if table_name not in self.in_memory_schemas:
            return False
        
        del self.in_memory_schemas[table_name]
        
        if self.collection:
            try:
                self.collection.delete(ids=[table_name])
            except Exception as e:
                print(f"Warning: Could not delete from ChromaDB: {e}")
        
        return True


schema_rag_service = SchemaRAGService()
