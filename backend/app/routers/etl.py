from fastapi import APIRouter, HTTPException
from ..models.schemas import ETLGenerateRequest, ETLGenerateResponse
from ..agents.intent_parser import IntentParserAgent
from ..agents.sql_generator import SQLGeneratorAgent
from ..services.schema_rag import schema_rag_service

router = APIRouter(prefix="/api/v1/etl", tags=["etl"])


@router.post("/generate", response_model=ETLGenerateResponse)
async def generate_etl(request: ETLGenerateRequest):
    try:
        intent_agent = IntentParserAgent()
        sql_agent = SQLGeneratorAgent()
        
        schemas = await schema_rag_service.search_schemas(request.query)
        schema_context = "\n".join([s["schema_info"] for s in schemas])
        
        intent_result = await intent_agent.run(request.query, schema_context)
        if not intent_result["success"]:
            return ETLGenerateResponse(
                success=False,
                error=intent_result["error"]
            )
        
        sql_result = await sql_agent.run(intent_result["intent"], schema_context)
        if not sql_result["success"]:
            return ETLGenerateResponse(
                success=False,
                error=sql_result["error"]
            )
        
        return ETLGenerateResponse(
            success=True,
            intent=intent_result["intent"],
            sql=sql_result["sql"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
