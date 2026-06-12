"""工作流 API 路由（支持多数据源 + 业务日期变量替换）"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from ..services.mysql_service import mysql_service
from ..services.script_runner import script_runner


router = APIRouter(prefix="/api/v1/workflow", tags=["工作流"])


# ==================== 数据模型 ====================

class FolderCreate(BaseModel):
    name: str
    parent_id: Optional[int] = None
    sort_order: int = 0


class FolderUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[int] = None
    sort_order: Optional[int] = None


class ScriptCreate(BaseModel):
    name: str
    folder_id: int
    data_source: Optional[str] = "pipeline"  # mysql / pipeline（数仓层）/ clickhouse
    sql_content: Optional[str] = ""
    schedule_cron: Optional[str] = None
    schedule_label: Optional[str] = None


class ScriptUpdate(BaseModel):
    name: Optional[str] = None
    folder_id: Optional[int] = None
    data_source: Optional[str] = None
    sql_content: Optional[str] = None
    schedule_cron: Optional[str] = None
    schedule_label: Optional[str] = None
    status: Optional[str] = None


class RunScriptRequest(BaseModel):
    bizdate: Optional[str] = None  # YYYY-MM-DD；若为空则使用今天


# ==================== 目录接口 ====================

@router.get("/folders")
async def list_folders():
    """获取所有目录"""
    query = """
        SELECT id, name, parent_id, sort_order, created_at, updated_at
        FROM workflow_folders
        ORDER BY sort_order ASC, id ASC
    """
    return mysql_service.execute_query(query)


@router.post("/folders")
async def create_folder(data: FolderCreate):
    """创建目录"""
    query = """
        INSERT INTO workflow_folders (name, parent_id, sort_order)
        VALUES (%s, %s, %s)
    """
    folder_id = mysql_service.execute_insert(
        query, (data.name, data.parent_id, data.sort_order)
    )
    if folder_id == 0:
        raise HTTPException(status_code=500, detail="创建目录失败")

    result = mysql_service.execute_query(
        "SELECT * FROM workflow_folders WHERE id = %s", (folder_id,)
    )
    return result[0] if result else None


@router.put("/folders/{folder_id}")
async def update_folder(folder_id: int, data: FolderUpdate):
    """更新目录"""
    updates = []
    params = []

    if data.name is not None:
        updates.append("name = %s")
        params.append(data.name)
    if data.parent_id is not None:
        updates.append("parent_id = %s")
        params.append(data.parent_id)
    if data.sort_order is not None:
        updates.append("sort_order = %s")
        params.append(data.sort_order)

    if not updates:
        raise HTTPException(status_code=400, detail="没有需要更新的字段")

    query = f"UPDATE workflow_folders SET {', '.join(updates)} WHERE id = %s"
    params.append(folder_id)

    affected = mysql_service.execute_update(query, tuple(params))
    if affected == 0:
        raise HTTPException(status_code=404, detail="目录不存在")

    result = mysql_service.execute_query(
        "SELECT * FROM workflow_folders WHERE id = %s", (folder_id,)
    )
    return result[0] if result else None


@router.delete("/folders/{folder_id}")
async def delete_folder(folder_id: int):
    """删除目录（会级联删除目录下的脚本）"""
    query = "DELETE FROM workflow_folders WHERE id = %s"
    affected = mysql_service.execute_update(query, (folder_id,))
    if affected == 0:
        raise HTTPException(status_code=404, detail="目录不存在")
    return {"message": "删除成功"}


# ==================== 脚本接口 ====================

@router.get("/scripts")
async def list_scripts(folder_id: Optional[int] = None):
    """获取所有脚本，或按目录筛选（含 sql_content 供前端展示）"""
    if folder_id:
        query = """
            SELECT id, name, folder_id, data_source, sql_content, schedule_cron,
                   schedule_label, status, last_run_at, created_at, updated_at
            FROM workflow_scripts
            WHERE folder_id = %s
            ORDER BY id ASC
        """
        return mysql_service.execute_query(query, (folder_id,))
    else:
        query = """
            SELECT id, name, folder_id, data_source, sql_content, schedule_cron,
                   schedule_label, status, last_run_at, created_at, updated_at
            FROM workflow_scripts
            ORDER BY id ASC
        """
        return mysql_service.execute_query(query)


@router.get("/scripts/{script_id}")
async def get_script(script_id: int):
    """获取单个脚本详情（含完整 sql_content）"""
    result = mysql_service.execute_query(
        "SELECT * FROM workflow_scripts WHERE id = %s", (script_id,)
    )
    if not result:
        raise HTTPException(status_code=404, detail="脚本不存在")
    return result[0]


@router.post("/scripts")
async def create_script(data: ScriptCreate):
    """创建脚本"""
    query = """
        INSERT INTO workflow_scripts (name, folder_id, data_source, sql_content, schedule_cron, schedule_label)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    script_id = mysql_service.execute_insert(
        query,
        (
            data.name,
            data.folder_id,
            (data.data_source or "maxcompute").lower(),
            data.sql_content,
            data.schedule_cron,
            data.schedule_label,
        ),
    )
    if script_id == 0:
        raise HTTPException(status_code=500, detail="创建脚本失败")

    result = mysql_service.execute_query(
        "SELECT * FROM workflow_scripts WHERE id = %s", (script_id,)
    )
    return result[0] if result else None


@router.put("/scripts/{script_id}")
async def update_script(script_id: int, data: ScriptUpdate):
    """更新脚本"""
    updates = []
    params = []

    if data.name is not None:
        updates.append("name = %s")
        params.append(data.name)
    if data.folder_id is not None:
        updates.append("folder_id = %s")
        params.append(data.folder_id)
    if data.data_source is not None:
        updates.append("data_source = %s")
        params.append(data.data_source.lower())
    if data.sql_content is not None:
        updates.append("sql_content = %s")
        params.append(data.sql_content)
    if data.schedule_cron is not None:
        updates.append("schedule_cron = %s")
        params.append(data.schedule_cron)
    if data.schedule_label is not None:
        updates.append("schedule_label = %s")
        params.append(data.schedule_label)
    if data.status is not None:
        updates.append("status = %s")
        params.append(data.status)

    if not updates:
        raise HTTPException(status_code=400, detail="没有需要更新的字段")

    updates.append("updated_at = NOW()")
    params.append(script_id)

    query = f"UPDATE workflow_scripts SET {', '.join(updates)} WHERE id = %s"
    affected = mysql_service.execute_update(query, tuple(params))
    if affected == 0:
        raise HTTPException(status_code=404, detail="脚本不存在")

    result = mysql_service.execute_query(
        "SELECT * FROM workflow_scripts WHERE id = %s", (script_id,)
    )
    return result[0] if result else None


@router.delete("/scripts/{script_id}")
async def delete_script(script_id: int):
    """删除脚本"""
    query = "DELETE FROM workflow_scripts WHERE id = %s"
    affected = mysql_service.execute_update(query, (script_id,))
    if affected == 0:
        raise HTTPException(status_code=404, detail="脚本不存在")
    return {"message": "删除成功"}


@router.post("/scripts/{script_id}/run")
async def run_script(script_id: int, req: Optional[RunScriptRequest] = None):
    """
    运行脚本（真实执行 SQL）
    - req.bizdate: 业务日期 YYYY-MM-DD，留空则使用今天
    - 执行时会把 SQL 中的 ${bizdate} 替换为实际值
    """
    bizdate_raw = (req.bizdate if req and req.bizdate else date.today().strftime("%Y-%m-%d"))

    # 校验日期格式
    try:
        datetime.strptime(bizdate_raw, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="bizdate 格式应为 YYYY-MM-DD")

    # 获取脚本内容和目录信息
    script = mysql_service.execute_query(
        "SELECT * FROM workflow_scripts WHERE id = %s", (script_id,)
    )
    if not script:
        raise HTTPException(status_code=404, detail="脚本不存在")

    script_data = script[0]
    sql_content = script_data.get("sql_content") or ""

    if not sql_content.strip():
        raise HTTPException(status_code=400, detail="脚本内容为空，无法执行")

    # 读取脚本的数据源
    data_source = (script_data.get("data_source") or "pipeline").lower()

    # 获取目录名（辅助脚本类型判断）
    folder_name = ""
    folder_id = script_data.get("folder_id")
    if folder_id:
        folder = mysql_service.execute_query(
            "SELECT name FROM workflow_folders WHERE id = %s", (folder_id,)
        )
        if folder:
            folder_name = folder[0].get("name", "")

    # 替换 SQL 中的 ${bizdate} 变量
    processed_sql = sql_content.replace("${bizdate}", bizdate_raw)
    # 兼容 $bizdate（无花括号）与 {bizdate} 写法
    processed_sql = processed_sql.replace("$bizdate", bizdate_raw)

    # 脚本类型检测
    script_type = script_runner.detect_script_type(processed_sql, folder_name)

    # 根据 data_source 决定执行器
    # mysql / pipeline（数仓层）-> mysql_service（按 data_source key 路由连接池）
    # clickhouse -> clickhouse_service
    if data_source == "clickhouse":
        effective_data_source = "clickhouse"
    else:
        effective_data_source = data_source  # mysql 或 pipeline

    result = script_runner.run(
        script_id,
        processed_sql,
        script_type=script_type,
        data_source=effective_data_source,
        bizdate=bizdate_raw,
    )

    return {
        "message": "脚本执行完成",
        "script_id": script_id,
        "data_source": data_source,
        "bizdate": bizdate_raw,
        "status": result["status"],
        "duration_ms": result["duration_ms"],
        "affected_rows": result.get("affected_rows", 0),
        "error": result.get("error_message"),
        "executed_statements": result.get("executed_statements", 0),
    }


# ==================== 日志接口 ====================

@router.get("/logs")
async def list_logs(script_id: Optional[int] = None, limit: int = 50):
    """获取运行日志"""
    if script_id:
        query = """
            SELECT id, script_id, data_source, bizdate, status, start_time,
                   end_time, duration_ms, error_message, created_at
            FROM workflow_logs
            WHERE script_id = %s
            ORDER BY start_time DESC
            LIMIT %s
        """
        return mysql_service.execute_query(query, (script_id, limit))
    else:
        query = """
            SELECT id, script_id, data_source, bizdate, status, start_time,
                   end_time, duration_ms, error_message, created_at
            FROM workflow_logs
            ORDER BY start_time DESC
            LIMIT %s
        """
        return mysql_service.execute_query(query, (limit,))


# ==================== 元信息接口 ====================

@router.get("/data-sources")
async def list_data_sources():
    """返回系统支持的数据源列表"""
    return [
        {
            "key": "pipeline",
            "label": "数仓层 (MySQL Pipeline)",
            "description": "数仓链路数据源（对应 local.yaml 中的 mysql-pipeline），支持 ${bizdate} 变量替换",
        },
        {
            "key": "mysql",
            "label": "工作流 MySQL",
            "description": "存储脚本/目录/日志的 MySQL 库（对应 local.yaml 中的 mysql）",
        },
        {
            "key": "clickhouse",
            "label": "ClickHouse",
            "description": "ADS 层输出同步目标",
        },
    ]
