"""数仓链路生成 - 提示词模板和输出模型"""
from __future__ import annotations

import json
from typing import List, Optional
from pydantic import BaseModel, Field


# ==================== Pydantic 输出模型 ====================

class TableField(BaseModel):
    """表字段"""
    name: str = Field(description="字段名")
    type: str = Field(description="字段类型")
    comment: str = Field(default="", description="字段注释")


class TableItem(BaseModel):
    """数仓表定义"""
    layer: str = Field(description="层级: dwd | dim | dws | ads")
    table_name: str = Field(description="表名")
    description: str = Field(default="", description="表描述")
    ddl_sql: str = Field(description="CREATE TABLE DDL 语句")
    insert_sql: str = Field(description="INSERT 语句")
    fields: List[TableField] = Field(default_factory=list, description="字段列表")
    depends_on: List[str] = Field(default_factory=list, description="依赖的上游表")


class ClickHouseTable(BaseModel):
    """ClickHouse 表"""
    source_ads_table: str = Field(description="MySQL ADS 表名")
    ch_table_name: str = Field(description="ClickHouse 表名")
    engine: str = Field(default="ReplacingMergeTree", description="引擎")
    order_by: str = Field(default="dt", description="ORDER BY")
    partition_by: str = Field(default="dt", description="分区字段")
    ddl_sql: str = Field(description="ClickHouse DDL")


class SyncScript(BaseModel):
    """同步脚本"""
    name: str = Field(description="脚本名称")
    source_table: str = Field(description="源表")
    target_table: str = Field(description="目标表")
    sync_fields: List[str] = Field(default_factory=list, description="同步字段")


class PipelineResult(BaseModel):
    """数仓链路生成结果"""
    demand_analysis: str = Field(description="需求分析，需要结合最新输入总结")
    tables: List[TableItem] = Field(description="数仓表列表")
    clickhouse_tables: List[ClickHouseTable] = Field(default_factory=list, description="ClickHouse 表")
    sync_scripts: List[SyncScript] = Field(default_factory=list, description="同步脚本")
    execution_order: List[str] = Field(default_factory=list, description="执行顺序")


# ==================== JSON Schema 转换工具 ====================

def get_schema_for_prompt(model: type[BaseModel]) -> str:
    """
    将 Pydantic 模型的 JSON Schema 转换为 prompt 友好的格式。
    
    处理逻辑：
    1. 展开 $ref 引用（将 $defs 中的定义内联到引用处）
    2. 移除 $defs 部分
    3. 格式化为易读的 JSON 字符串
    4. 转义 { 和 } 为 {{ 和 }}，避免被 LangChain 解析为变量
    
    Args:
        model: Pydantic 模型类
        
    Returns:
        格式化后的 JSON 字符串，可直接嵌入 prompt
    """
    schema = model.model_json_schema()
    
    # 提取 $defs（如果有）
    defs = schema.pop("$defs", {})
    
    # 递归展开 $ref
    def resolve_refs(obj):
        if isinstance(obj, dict):
            if "$ref" in obj:
                ref_path = obj["$ref"]
                # 处理 #/$defs/XXX 格式
                if ref_path.startswith("#/$defs/"):
                    ref_name = ref_path.split("/")[-1]
                    if ref_name in defs:
                        return resolve_refs(defs[ref_name])
                return obj
            return {k: resolve_refs(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [resolve_refs(item) for item in obj]
        return obj
    
    resolved_schema = resolve_refs(schema)
    
    # 格式化为 JSON 字符串
    json_str = json.dumps(resolved_schema, ensure_ascii=False, indent=2)
    
    # 转义 { 和 } 为 {{ 和 }}，避免被 LangChain 解析为变量
    json_str = json_str.replace("{", "{{").replace("}", "}}")
    
    return json_str


# ==================== 提示词模板 ====================

SYSTEM_RULES = """你是一个专业的数据仓库工程师，擅长根据业务需求设计完整的数据分层链路。

## 数仓分层规则
- ODS 层: 原始业务数据，只能作为源表，不能作为生成的表名
- DWD 层: 对 ODS 清洗去重
- DIM 层: 维度表，从 ODS 抽取并去重
- DWS 层: 轻度聚合，DWD + DIM
- ADS 层: 面向应用的宽表

## MySQL 建表规范
- 表名格式: pipeline.{{层级}}_{{业务描述}}
- DWD/DWS/ADS/DIM 必须包含 dt DATE 字段
- DDL 使用 CREATE TABLE IF NOT EXISTS
- INSERT 使用 ${{bizdate}} 变量

## ClickHouse 规范
- 表名格式: report.{{ads_表名}}
- 使用 ReplacingMergeTree 引擎
- ORDER BY 选择区分度高的字段
- PARTITION BY toYYYYMMDD(dt)

## 同步脚本
- 从 MySQL ADS 同步到 ClickHouse
- 粒度为全量覆盖

## 输出要求
你必须返回严格的 JSON 格式，包含以上定义的字段。不要输出任何额外文本，只返回 JSON 文本。输出 JSON 模式如下：
"""
