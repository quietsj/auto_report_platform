from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime


class QueryRequest(BaseModel):
    query: str


class IntentParseResponse(BaseModel):
    success: bool
    intent: Optional[str] = None
    error: Optional[str] = None


class SQLGenerateRequest(BaseModel):
    intent: str
    schema_info: str


class SQLGenerateResponse(BaseModel):
    success: bool
    sql: Optional[str] = None
    error: Optional[str] = None


class ETLGenerateRequest(BaseModel):
    query: str
    auto_publish: bool = False


class ETLGenerateResponse(BaseModel):
    success: bool
    intent: Optional[str] = None
    sql: Optional[str] = None
    node_id: Optional[str] = None
    error: Optional[str] = None


class SchemaAddRequest(BaseModel):
    table_name: str
    schema_info: str
    metadata: Optional[Dict[str, Any]] = None


class SchemaSearchRequest(BaseModel):
    query: str
    top_k: int = 3


class QueryExecuteRequest(BaseModel):
    sql: str


class ReportConfig(BaseModel):
    chart_type: str
    title: str
    x_axis: Optional[str] = None
    y_axis: Optional[str] = None
    dimensions: Optional[List[str]] = None
    metrics: Optional[List[str]] = None
