from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from ..agents.report_builder import ReportBuilderAgent

router = APIRouter(prefix="/api/v1/report", tags=["report"])


@router.post("/generate")
async def generate_report(data: Dict[str, Any]):
    try:
        report_agent = ReportBuilderAgent()
        intent = data.get("intent", "")
        result = await report_agent.run(data.get("data", {}), intent)
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["error"])
        
        return {"success": True, "config": result["config"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
