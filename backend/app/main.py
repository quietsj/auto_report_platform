from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.config import settings
from .routers import etl, query, workflow, report_api, clickhouse, chat, knowledge
from .services.mysql_service import mysql_service


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(etl.router)
app.include_router(query.router)
app.include_router(report_api.router)
app.include_router(workflow.router)
app.include_router(clickhouse.router)
app.include_router(chat.router)
app.include_router(knowledge.router)


@app.on_event("startup")
async def on_startup():
    """应用启动时：确保工作流相关表存在并补齐字段"""
    mysql_service.ensure_workflow_tables(data_source="mysql")


@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
