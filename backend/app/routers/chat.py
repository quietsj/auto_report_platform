"""数仓链路生成路由"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from ..agents.pipeline_agent import PipelineAgent
from ..services.mysql_service import mysql_service
from ..core.session_manager import session_manager
from langchain_core.messages import HumanMessage, AIMessage


router = APIRouter(prefix="/api/v1/chat", tags=["对话开发"])


# ==================== 请求/响应模型 ====================

class PipelineRequest(BaseModel):
    user_input: str
    model: Optional[str] = "deepseek-v4-pro"
    session_id: Optional[str] = None  # 会话 ID，用于多轮对话
    chunk_size: Optional[int] = 1500
    custom_separators: Optional[List[str]] = None
    context: Optional[Dict[str, Any]] = None


class PersistRequest(BaseModel):
    demand_analysis: str
    tables: List[Dict[str, Any]]
    clickhouse_tables: List[Dict[str, Any]]
    sync_scripts: List[Dict[str, Any]]
    execution_order: List[str]
    report_cfg: Optional[Dict[str, Any]] = None


# ==================== 目录名映射 ====================

LAYER_FOLDER_MAP = {
    "dwd": "DWD层",
    "dim": "DIM层",
    "dws": "DWS层",
    "ads": "ADS层",
    "clickhouse": "ClickHouse同步",
}


# ==================== 会话管理接口 ====================

@router.get("/sessions")
async def list_sessions():
    """获取所有会话列表"""
    return {
        "sessions": session_manager.list_sessions()
    }


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """获取指定会话的详情"""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {
        "session_id": session.session_id,
        "messages": [m.model_dump() for m in session.messages],
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    }


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除指定会话"""
    if session_manager.delete_session(session_id):
        return {"message": "删除成功"}
    raise HTTPException(status_code=404, detail="会话不存在")


@router.post("/sessions/clear/{session_id}")
async def clear_session(session_id: str):
    """清空会话历史（保留会话）"""
    if session_manager.clear_session(session_id):
        return {"message": "会话已清空"}
    raise HTTPException(status_code=404, detail="会话不存在")


# ==================== 对话生成接口 ====================

@router.post("/pipeline")
async def generate_pipeline(req: PipelineRequest):
    """
    根据用户需求生成完整数仓链路，支持多轮会话

    Args:
        user_input: 用户需求描述
        model: 模型名称（deepseek-v4-pro / deepseek-v4-flash）
        session_id: 会话 ID，不传则创建新会话
        chunk_size: 向量数据库块大小（默认 1500）
        custom_separators: 自定义分隔符列表（默认 [';', ',', ' ']）
        context: 可选业务上下文
    """
    model_name = req.model or "deepseek-v4-pro"
    if model_name not in ("deepseek-v4-pro", "deepseek-v4-flash"):
        model_name = "deepseek-v4-pro"

    # 会话管理：如果 session_id 为空，创建新会话
    session_id = req.session_id
    if not session_id:
        session_id = session_manager.create_session()
        print(f"[chat/pipeline] 创建新会话: {session_id}")
    else:
        # 确保会话存在
        if not session_manager.get_session(session_id):
            session_manager.create_session(session_id)
            print(f"[chat/pipeline] 会话不存在，重新创建: {session_id}")

    # 创建 Agent
    agent = PipelineAgent(model=model_name, session_id=session_id)

    # 从 session_manager 获取 llm_history（持久化，跨请求保存历史）
    llm_history = session_manager.get_llm_history(session_id)
    print(f"[chat/pipeline] 获取 LLM 历史: session={session_id}, history_size={len(llm_history.messages) if llm_history else 0}")

    # 执行对话生成（传入 session_manager，由 Agent 内部获取 LLM 历史）
    result = await agent.run(user_input=req.user_input, context=req.context, session_manager=session_manager)

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "生成失败"))

    return {
        "session_id": session_id,
        "demand_analysis": result.get("demand_analysis"),
        "tables": result.get("tables", []),
        "clickhouse_tables": result.get("clickhouse_tables", []),
        "sync_scripts": result.get("sync_scripts", []),
        "execution_order": result.get("execution_order", []),
        "model_used": model_name,
        "chunk_size": req.chunk_size or 1500,
        "custom_separators": req.custom_separators or [";", ",", " "],
    }


# ==================== 写入工作流接口 ====================

@router.post("/persist")
async def persist_pipeline(req: PersistRequest):
    """
    将生成的链路一键写入工作流：
    - MySQL 数仓层脚本（DWD/DWS/ADS）写入 pipeline 目录
    - ClickHouse 建表脚本写入 clickhouse 目录
    - 同步脚本（INSERT INTO ... SELECT）写入 clickhouse 目录
    - 所有脚本需在工作流页面手动点击"运行脚本"执行
    - 报表配置直接写入 report_metadata 等表
    """
    folder_id_map: Dict[str, int] = {}
    script_id_map: Dict[str, int] = {}

    # 1. 确保目录存在
    for layer_key, folder_name in LAYER_FOLDER_MAP.items():
        existing = mysql_service.execute_query(
            "SELECT id FROM workflow_folders WHERE name = %s LIMIT 1",
            (folder_name,)
        )
        if existing:
            folder_id_map[layer_key] = existing[0]["id"]
        else:
            folder_id = mysql_service.execute_insert(
                "INSERT INTO workflow_folders (name, sort_order) VALUES (%s, %s)",
                (folder_name, 0)
            )
            if folder_id == 0:
                raise HTTPException(status_code=500, detail=f"创建目录 {folder_name} 失败")
            folder_id_map[layer_key] = folder_id
            print(f"[chat/persist] 创建目录: {folder_name} -> id={folder_id}")

    # 2. 写入 MySQL 表脚本（DWD / DIM / DWS / ADS）
    for table in req.tables:
        layer = table.get("layer", "ads")
        folder_key = layer.lower()
        folder_id = folder_id_map.get(folder_key, folder_id_map.get("ads"))

        table_name = table.get("table_name", "unknown_table")
        ddl_sql = table.get("ddl_sql", "")
        insert_sql = table.get("insert_sql", "")

        full_sql = ddl_sql.strip()
        if insert_sql.strip():
            full_sql += "\n\n-- 数据加工逻辑\n" + insert_sql.strip()

        script_id = _create_script(
            name=table_name,
            folder_id=folder_id,
            sql_content=full_sql,
            schedule_label="手动触发",
            data_source="pipeline",
        )
        script_id_map[f"mysql_{table_name}"] = script_id
        print(f"[chat/persist] 创建 MySQL 脚本: {table_name} -> id={script_id}")

    # 3. 写入 ClickHouse 建表脚本（仅写入，由用户在工作流页面手动执行）
    for ch_table in req.clickhouse_tables:
        ch_table_name = ch_table.get("ch_table_name", "unknown_ch_table")
        ddl_sql = ch_table.get("ddl_sql", "")

        script_id = _create_script(
            name=ch_table_name,
            folder_id=folder_id_map.get("clickhouse"),
            sql_content=ddl_sql,
            schedule_label="手动触发",
            data_source="clickhouse",
        )
        script_id_map[f"clickhouse_{ch_table_name}"] = script_id
        print(f"[chat/persist] 写入 ClickHouse 建表脚本: {ch_table_name} -> id={script_id}")

    # 4. 写入同步脚本（INSERT INTO ... SELECT）—— 仅写入，由用户在工作流页面手动执行
    for sync in req.sync_scripts:
        sync_name = sync.get("name", sync.get("target_table", "sync_script"))
        sync_fields = sync.get("sync_fields", [])
        filter_condition = sync.get("filter_condition", "")
        source_table = sync.get("source_table", "")
        target_table = sync.get("target_table", "")

        # 构建 INSERT INTO ... SELECT 语句（保留 ${bizdate} 变量，运行时由 script_runner 替换）
        if sync_fields and source_table and target_table:
            field_str = ", ".join(sync_fields)
            where_clause = f"WHERE {filter_condition}" if filter_condition else ""
            # 处理 target_table 可能已经包含 report. 前缀的情况
            target_full_table = target_table if target_table.startswith("report.") else f"report.{target_table}"
            sync_sql = f"INSERT INTO {target_full_table} ({field_str}) SELECT {field_str} FROM {source_table} {where_clause}"
        else:
            target_full_table = target_table if target_table.startswith("report.") else f"report.{target_table}"
            sync_sql = f"-- 同步配置: {sync_name}\n-- 源表: {source_table} -> 目标表: {target_full_table}"

        script_id = _create_script(
            name=sync_name,
            folder_id=folder_id_map.get("clickhouse"),
            sql_content=sync_sql,
            schedule_label="手动触发",
            data_source="clickhouse",
        )
        script_id_map[f"sync_{target_table}"] = script_id
        print(f"[chat/persist] 写入同步脚本: {sync_name} -> id={script_id}")

    # 5. 写入报表配置
    report_id = None
    if req.report_cfg:
        report_cfg = req.report_cfg
        try:
            # 写入 report_metadata
            report_id = mysql_service.execute_insert(
                """INSERT INTO report_metadata
                   (name, description, category, is_published, view_count, created_by, default_table, data_source_name)
                   VALUES (%s, %s, %s, 1, 0, 'AI生成', %s, %s)""",
                (
                    report_cfg.get("report_name", "未命名报表"),
                    report_cfg.get("report_desc", ""),
                    report_cfg.get("category", "AI生成"),
                    report_cfg.get("ch_table_name", ""),
                    "clickhouse",
                )
            )
            print(f"[chat/persist] 创建报表: {report_cfg.get('report_name')} -> id={report_id}")

            # 写入维度字段
            for i, dim_field in enumerate(report_cfg.get("dimension_fields", [])):
                mysql_service.execute_insert(
                    """INSERT INTO report_data_config
                       (report_id, field_name, field_alias, field_type, data_type, sort_order, is_visible)
                       VALUES (%s, %s, %s, 'dimension', 'string', %s, 1)""",
                    (report_id, dim_field, dim_field, i)
                )

            # 写入指标字段
            for i, metric_field in enumerate(report_cfg.get("metric_fields", [])):
                mysql_service.execute_insert(
                    """INSERT INTO report_data_config
                       (report_id, field_name, field_alias, field_type, data_type, aggregation_type, sort_order, is_visible)
                       VALUES (%s, %s, %s, 'metric', 'number', 'SUM', %s, 1)""",
                    (report_id, metric_field, metric_field, i + len(report_cfg.get("dimension_fields", [])))
                )

            # 写入图表配置
            suggested_chart = report_cfg.get("suggested_chart", "line")
            chart_title = report_cfg.get("suggested_chart_label") or f"{report_cfg.get('report_name', '报表')} - {suggested_chart}"
            mysql_service.execute_insert(
                """INSERT INTO report_chart_configs
                   (report_id, chart_type, title, config, layout_order)
                   VALUES (%s, %s, %s, %s, 1)""",
                (
                    report_id,
                    suggested_chart,
                    chart_title,
                    '{"xField": "", "yField": ""}',
                )
            )
            print(f"[chat/persist] 报表字段和图表配置写入完成: report_id={report_id}")

        except Exception as e:
            print(f"[chat/persist] 报表配置写入失败: {e}")
            # 不阻断主流程，报表配置失败不影响脚本写入

    return {
        "message": "写入成功",
        "folder_id_map": folder_id_map,
        "script_id_map": script_id_map,
        "report_id": report_id,
    }


def _create_script(
    name: str,
    folder_id: int,
    sql_content: str,
    schedule_label: str,
    data_source: str = "pipeline",
) -> int:
    """创建脚本，处理重复名称，并写入 data_source 字段"""
    # 检查是否已存在同名脚本
    existing = mysql_service.execute_query(
        "SELECT id FROM workflow_scripts WHERE name = %s AND folder_id = %s LIMIT 1",
        (name, folder_id)
    )
    if existing:
        # 更新现有脚本内容 + data_source
        mysql_service.execute_update(
            "UPDATE workflow_scripts SET sql_content = %s, data_source = %s, updated_at = NOW() WHERE id = %s",
            (sql_content, data_source, existing[0]["id"])
        )
        return existing[0]["id"]

    # 生成唯一名称（带序号）
    final_name = name
    counter = 2
    while True:
        check = mysql_service.execute_query(
            "SELECT id FROM workflow_scripts WHERE name = %s LIMIT 1",
            (final_name,)
        )
        if not check:
            break
        final_name = f"{name}_{counter}"
        counter += 1

    script_id = mysql_service.execute_insert(
        """INSERT INTO workflow_scripts (name, folder_id, data_source, sql_content, schedule_label, status)
           VALUES (%s, %s, %s, %s, %s, 'idle')""",
        (final_name, folder_id, data_source, sql_content, schedule_label)
    )
    return script_id
