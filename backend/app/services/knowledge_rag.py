"""知识库 RAG 服务 - 直接与 ChromaDB 交互，无内存缓存"""
from __future__ import annotations

import asyncio
import hashlib
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from langchain.text_splitter import RecursiveCharacterTextSplitter


@dataclass
class TextChunk:
    """文本分块"""
    id: str
    content: str
    chunk_index: int
    total_chunks: int
    source_name: str
    metadata: Dict[str, Any]


class KnowledgeRAGService:
    """知识库 RAG 服务 - 直接与 ChromaDB 交互，无内存缓存层"""

    def __init__(self):
        self.client = None
        self.collection = None

        try:
            import chromadb
            from ..core.config import settings
            self.client = chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
            self.collection = self.client.get_or_create_collection("knowledge_base")
            print("[KnowledgeRAG] ChromaDB 连接成功，collection: knowledge_base")
        except Exception as e:
            print(f"[KnowledgeRAG] ChromaDB 连接失败: {e}")

    # ============================================================
    # 导入
    # ============================================================

    async def import_text(
        self,
        text: str,
        source_name: str,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        custom_separators: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """导入文本并分块写入向量数据库"""
        if not text or not text.strip():
            raise ValueError("文本内容不能为空")

        # 分块
        if custom_separators and len(custom_separators) > 0:
            separators = custom_separators
        else:
            separators = ["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators,
            length_function=len,
        )
        raw_chunks = splitter.split_text(text.strip())
        if not raw_chunks:
            raise ValueError("文本分块后为空，请检查文本内容")

        total_chunks = len(raw_chunks)
        doc_id = hashlib.md5(source_name.encode()).hexdigest()[:16]

        if not self.collection:
            raise Exception("ChromaDB 不可用，无法导入")

        # 删除旧文档
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.collection.delete(where={"doc_id": doc_id})
            )
        except Exception as e:
            print(f"[KnowledgeRAG] 删除旧文档失败: {e}")

        # 获取嵌入向量
        from ..core.embedding_service import embedding_service
        embeddings = await embedding_service.embed_batch(raw_chunks)

        # 批量写入 ChromaDB
        chunk_ids = [f"{doc_id}_{idx}" for idx in range(len(raw_chunks))]
        metadatas = [
            {
                "chunk_size": len(raw_chunks[idx]),
                "chunk_index": idx,
                "total_chunks": total_chunks,
                "doc_id": doc_id,
                "source_name": source_name,
            }
            for idx in range(len(raw_chunks))
        ]

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self.collection.add(
                documents=raw_chunks,
                embeddings=embeddings,
                metadatas=metadatas,
                ids=chunk_ids,
            )
        )

        count_result = await loop.run_in_executor(None, lambda: self.collection.count())
        print(f"[KnowledgeRAG] 导入完成: {source_name} -> {total_chunks} 个块，collection 总记录: {count_result}")

        return {
            "doc_id": doc_id,
            "source_name": source_name,
            "total_chunks": total_chunks,
            "added_to_vector_db": total_chunks,
            "chunks": [
                {
                    "id": f"{doc_id}_{idx}",
                    "content_preview": t[:100] + "..." if len(t) > 100 else t,
                    "chunk_index": idx,
                    "total_chunks": total_chunks,
                }
                for idx, t in enumerate(raw_chunks)
            ]
        }

    # ============================================================
    # 检索
    # ============================================================

    async def search(
        self,
        query: str,
        top_k: int = 5,
        doc_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """检索相关文本块，直接查 ChromaDB"""
        if not self.collection:
            print("[KnowledgeRAG] ChromaDB 不可用，检索返回空")
            return []

        try:
            from ..core.embedding_service import embedding_service
            query_embedding = await embedding_service.embed(query)

            if not isinstance(query_embedding, list):
                raise Exception(f"Embedding 返回异常: {query_embedding}")

            loop = asyncio.get_event_loop()
            if doc_id:
                search_results = await loop.run_in_executor(
                    None,
                    lambda: self.collection.query(
                        query_embeddings=[query_embedding],
                        n_results=top_k,
                        where={"doc_id": doc_id},
                    )
                )
            else:
                search_results = await loop.run_in_executor(
                    None,
                    lambda: self.collection.query(
                        query_embeddings=[query_embedding],
                        n_results=top_k,
                    )
                )

            ids_list = search_results.get("ids", [[]])[0]
            docs_list = search_results.get("documents", [[]])[0]
            metas_list = search_results.get("metadatas", [[]])[0]
            dists_list = search_results.get("distances", [[]])[0]

            results = []
            for i in range(len(ids_list)):
                cid = ids_list[i]
                content = docs_list[i] if i < len(docs_list) else ""
                meta = metas_list[i] if i < len(metas_list) else {}
                if not isinstance(meta, dict):
                    meta = {}
                distance = dists_list[i] if i < len(dists_list) else 0.0

                results.append({
                    "chunk_id": cid,
                    "content": content,
                    "metadata": meta,
                    "distance": distance,
                    "score": 1 - distance,
                })

            print(f"[KnowledgeRAG] 检索完成，命中 {len(results)} 条")
            return results

        except Exception as e:
            print(f"[KnowledgeRAG] ChromaDB 检索失败: {e}")
            import traceback
            traceback.print_exc()
            return []

    # ============================================================
    # 列表 / 统计 / 删除
    # ============================================================

    async def list_documents(self) -> List[Dict[str, Any]]:
        """列出所有已导入的文档"""
        if not self.collection:
            return []

        try:
            loop = asyncio.get_event_loop()
            count = await loop.run_in_executor(None, lambda: self.collection.count())
            if count == 0:
                return []

            # 分批获取所有数据，按 doc_id 聚合
            batch_size = 500
            offset = 0
            doc_map: Dict[str, Dict[str, Any]] = {}

            while offset < count:
                batch = await loop.run_in_executor(
                    None,
                    lambda: self.collection.get(
                        include=["metadatas"],
                        limit=batch_size,
                        offset=offset,
                    )
                )
                ids = batch.get("ids", [])
                metas = batch.get("metadatas", [])

                for i, cid in enumerate(ids):
                    meta = metas[i] if i < len(metas) else {}
                    if not isinstance(meta, dict):
                        meta = {}
                    doc_id = meta.get("doc_id", "")
                    source_name = meta.get("source_name", "unknown")

                    if doc_id and doc_id not in doc_map:
                        doc_map[doc_id] = {
                            "doc_id": doc_id,
                            "source_name": source_name,
                            "total_chunks": 0,
                        }
                    if doc_id:
                        doc_map[doc_id]["total_chunks"] += 1

                offset += batch_size

            return list(doc_map.values())

        except Exception as e:
            print(f"[KnowledgeRAG] 列出文档失败: {e}")
            import traceback
            traceback.print_exc()
            return []

    async def delete_document(self, doc_id: str) -> bool:
        """删除指定文档的所有块"""
        if not self.collection:
            return False

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.collection.delete(where={"doc_id": doc_id})
            )
            print(f"[KnowledgeRAG] 已删除文档 {doc_id}")
            return True
        except Exception as e:
            print(f"[KnowledgeRAG] 删除文档失败: {e}")
            return False

    async def get_chunk_stats(self) -> Dict[str, Any]:
        """获取知识库统计信息"""
        if not self.collection:
            return {"total_documents": 0, "total_chunks": 0, "avg_chunk_size": 0}

        try:
            loop = asyncio.get_event_loop()
            total_chunks = await loop.run_in_executor(None, lambda: self.collection.count())
            if total_chunks == 0:
                return {"total_documents": 0, "total_chunks": 0, "avg_chunk_size": 0}

            # 分批获取所有 metadata 以计算文档数和平均块大小
            batch_size = 500
            offset = 0
            doc_ids: set = set()
            total_size = 0
            size_count = 0

            while offset < total_chunks:
                batch = await loop.run_in_executor(
                    None,
                    lambda: self.collection.get(
                        include=["metadatas", "documents"],
                        limit=batch_size,
                        offset=offset,
                    )
                )
                metas = batch.get("metadatas", [])
                docs = batch.get("documents", [])

                for i, meta in enumerate(metas):
                    if isinstance(meta, dict):
                        doc_id = meta.get("doc_id")
                        if doc_id:
                            doc_ids.add(doc_id)
                        chunk_size = meta.get("chunk_size")
                        if isinstance(chunk_size, (int, float)):
                            total_size += chunk_size
                            size_count += 1
                    elif i < len(docs) and isinstance(docs[i], str):
                        total_size += len(docs[i])
                        size_count += 1

                offset += batch_size

            total_documents = len(doc_ids)
            avg_chunk_size = (total_size / size_count) if size_count > 0 else 0

            return {
                "total_documents": total_documents,
                "total_chunks": total_chunks,
                "avg_chunk_size": avg_chunk_size,
            }
        except Exception as e:
            print(f"[KnowledgeRAG] 获取统计失败: {e}")
            return {"total_documents": 0, "total_chunks": 0, "avg_chunk_size": 0}


# 全局单例
knowledge_rag_service = KnowledgeRAGService()
