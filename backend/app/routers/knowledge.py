"""知识库 API 路由 - 支持文本导入、分块、检索"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, List
from ..services.knowledge_rag import knowledge_rag_service


router = APIRouter(prefix="/api/v1/knowledge", tags=["知识库"])


# ==================== 请求/响应模型 ====================

class TextImportRequest(BaseModel):
    """文本导入请求"""
    text: str
    source_name: str
    chunk_size: int = 500
    chunk_overlap: int = 50
    custom_separators: Optional[List[str]] = None


class TextSearchRequest(BaseModel):
    """文本检索请求"""
    query: str
    top_k: int = 5
    doc_id: Optional[str] = None


# ==================== 导入接口 ====================

@router.post("/import/text")
async def import_text(req: TextImportRequest):
    """
    导入文本内容，自动分块并写入向量数据库

    - text: 原始文本内容
    - source_name: 来源名称（如文件名）
    - chunk_size: 每个块的目标字符数（默认 500）
    - chunk_overlap: 块之间重叠字符数（默认 50）
    - custom_separators: 自定义分隔符列表，默认为段落/换行/标点符号
    """
    try:
        result = await knowledge_rag_service.import_text(
            text=req.text,
            source_name=req.source_name,
            chunk_size=req.chunk_size,
            chunk_overlap=req.chunk_overlap,
            custom_separators=req.custom_separators,
        )
        return {"success": True, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


@router.post("/import/file")
async def import_file(
    source_name: str = Form(...),
    chunk_size: int = Form(500),
    chunk_overlap: int = Form(50),
    custom_separators: Optional[str] = Form(None),
    file: UploadFile = File(...),
):
    """
    导入文本文件（支持 .txt/.md/.csv/.sql），自动分块并写入向量数据库

    - source_name: 来源名称
    - chunk_size: 每个块的目标字符数
    - chunk_overlap: 块之间重叠字符数
    - custom_separators: 可选，自定义分隔符 JSON 数组字符串
    - file: 上传的文本文件
    """
    import json
    parsed_separators: Optional[List[str]] = None
    if custom_separators:
        try:
            parsed_separators = json.loads(custom_separators)
        except json.JSONDecodeError:
            pass

    try:
        # 读取文件内容
        content = await file.read()

        # 检测编码
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = content.decode("gbk")
            except UnicodeDecodeError:
                text = content.decode("utf-8", errors="ignore")

        if not text.strip():
            raise HTTPException(status_code=400, detail="文件内容为空")

        result = await knowledge_rag_service.import_text(
            text=text,
            source_name=source_name or file.filename or "unknown",
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            custom_separators=parsed_separators,
        )
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件导入失败: {str(e)}")


# ==================== 检索接口 ====================

@router.post("/search")
async def search_knowledge(req: TextSearchRequest):
    """
    检索知识库中与查询最相关的文本块

    - query: 查询文本
    - top_k: 返回前 K 个结果（默认 5）
    - doc_id: 可选，限定只检索指定文档
    """
    try:
        results = await knowledge_rag_service.search(
            query=req.query,
            top_k=req.top_k,
            doc_id=req.doc_id,
        )
        return {"success": True, "data": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检索失败: {str(e)}")


# ==================== 文档管理接口 ====================

@router.get("/documents")
async def list_documents():
    """列出所有已导入的文档"""
    try:
        docs = await knowledge_rag_service.list_documents()
        stats = await knowledge_rag_service.get_chunk_stats()
        return {
            "success": True,
            "data": {
                "documents": docs,
                "stats": stats,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取文档列表失败: {str(e)}")


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    """删除指定文档（及其所有分块）"""
    try:
        success = await knowledge_rag_service.delete_document(doc_id)
        return {
            "success": success,
            "message": "文档已删除" if success else "文档不存在"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除文档失败: {str(e)}")


@router.get("/stats")
async def get_stats():
    """获取知识库统计信息"""
    try:
        stats = await knowledge_rag_service.get_chunk_stats()
        return {"success": True, "data": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计失败: {str(e)}")
