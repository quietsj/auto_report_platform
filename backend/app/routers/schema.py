from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from ..models.schemas import SchemaAddRequest, SchemaSearchRequest
from ..services.schema_rag import schema_rag_service

router = APIRouter(prefix="/api/v1/schema", tags=["schema"])


@router.post("/add")
async def add_schema(request: SchemaAddRequest):
    try:
        await schema_rag_service.add_schema(
            request.table_name,
            request.schema_info,
            request.metadata
        )
        return {"success": True, "message": "Schema added successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def search_schemas(request: SchemaSearchRequest):
    try:
        schemas = await schema_rag_service.search_schemas(request.query, request.top_k)
        return {"success": True, "data": schemas}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_tables():
    try:
        tables = schema_rag_service.list_tables()
        return {"success": True, "data": tables}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
