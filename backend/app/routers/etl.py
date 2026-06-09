from fastapi import APIRouter
from ..models.schemas import ETLGenerateRequest, ETLGenerateResponse
from ..services.schema_rag import schema_rag_service

router = APIRouter(prefix="/api/v1/etl", tags=["etl"])


@router.post("/generate", response_model=ETLGenerateResponse)
async def generate_etl(request: ETLGenerateRequest):
    try:
        schemas = await schema_rag_service.search_schemas(request.query)
        
        if not schemas:
            return ETLGenerateResponse(
                success=True,
                intent=f"解析查询: {request.query}",
                sql=f"-- 请先在 'ETL 编辑器' 中添加表结构\n-- 示例 SQL:\nSELECT * FROM example_table WHERE date >= '2024-01-01' LIMIT 100"
            )
        
        tables = [s["table_name"] for s in schemas]
        example_table = tables[0]
        
        result = ETLGenerateResponse(
            success=True,
            intent=f"查询分析: {request.query}\n\n相关表: {', '.join(tables)}",
            sql=f"-- 自动生成的示例 SQL\nSELECT * \nFROM {example_table}\nWHERE date >= '2024-01-01'\nLIMIT 100"
        )
        
        return result
    except Exception as e:
        return ETLGenerateResponse(
            success=False,
            error=str(e)
        )
