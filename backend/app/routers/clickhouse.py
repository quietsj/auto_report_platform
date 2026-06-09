"""ClickHouse API 路由"""
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Optional
from ..services.clickhouse_service import clickhouse_service


router = APIRouter(prefix="/api/v1/clickhouse", tags=["ClickHouse"])


@router.get("/databases", response_model=List[str])
async def list_databases():
    """获取所有数据库"""
    try:
        return clickhouse_service.get_databases()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tables", response_model=List[Dict[str, str]])
async def list_tables(database: Optional[str] = None):
    """获取指定数据库的表列表"""
    try:
        return clickhouse_service.get_tables(database)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tables/{table_name}/schema", response_model=List[Dict])
async def get_table_schema(table_name: str, database: Optional[str] = None):
    """获取表的字段结构"""
    try:
        return clickhouse_service.get_table_schema(table_name, database)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tables/{table_name}/sample", response_model=List[Dict])
async def get_sample_data(table_name: str, database: Optional[str] = None, limit: int = 100):
    """获取表的样本数据"""
    try:
        return clickhouse_service.get_sample_data(table_name, database, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query")
async def execute_sql(query: Dict[str, str]):
    """执行 SQL 查询"""
    sql = query.get("sql")
    if not sql:
        raise HTTPException(status_code=400, detail="缺少 SQL 查询语句")
    
    try:
        result = clickhouse_service.execute_query(sql)
        return {"success": True, "data": result, "total": len(result)}
    except Exception as e:
        return {"success": False, "error": str(e), "data": []}


@router.get("/tables/{table_name}/columns/{column_name}/stats")
async def get_column_stats(table_name: str, column_name: str, database: Optional[str] = None):
    """获取字段统计信息"""
    try:
        return clickhouse_service.get_column_stats(table_name, column_name, database)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
