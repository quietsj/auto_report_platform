from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from ..models.schemas import QueryExecuteRequest
from ..services.clickhouse_service import clickhouse_service

router = APIRouter(prefix="/api/v1/query", tags=["query"])


@router.post("/execute")
async def execute_query(request: QueryExecuteRequest):
    try:
        result = await clickhouse_service.execute_query(request.sql)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
