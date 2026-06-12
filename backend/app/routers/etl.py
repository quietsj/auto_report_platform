"""ETL 路由 - 已禁用 schema 相关功能"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/etl", tags=["etl"])


@router.post("/generate")
async def generate_etl():
    """ETL 生成接口已禁用（schema 功能已移除）"""
    return {
        "success": False,
        "error": "ETL schema 功能已禁用，请使用知识库模块进行 RAG 检索"
    }
