"""工作流 API 路由"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from ..services.mysql_service import mysql_service


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
    sql_content: Optional[str] = ""
    schedule_cron: Optional[str] = None
    schedule_label: Optional[str] = None


class ScriptUpdate(BaseModel):
    name: Optional[str] = None
    folder_id: Optional[int] = None
    sql_content: Optional[str] = None
    schedule_cron: Optional[str] = None
    schedule_label: Optional[str] = None
    status: Optional[str] = None


class FolderResponse(BaseModel):
    id: int
    name: str
    parent_id: Optional[int]
    sort_order: int
    created_at: datetime
    updated_at: datetime


class ScriptResponse(BaseModel):
    id: int
    name: str
    folder_id: int
    sql_content: Optional[str]
    schedule_cron: Optional[str]
    schedule_label: Optional[str]
    status: str
    last_run_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class LogResponse(BaseModel):
    id: int
    script_id: int
    status: str
    start_time: datetime
    end_time: Optional[datetime]
    duration_ms: Optional[int]
    error_message: Optional[str]
    created_at: datetime


# ==================== 目录接口 ====================

@router.get("/folders", response_model=List[FolderResponse])
async def list_folders():
    """获取所有目录"""
    query = """
        SELECT id, name, parent_id, sort_order, created_at, updated_at
        FROM workflow_folders
        ORDER BY sort_order ASC, id ASC
    """
    return mysql_service.execute_query(query)


@router.post("/folders", response_model=FolderResponse)
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


@router.put("/folders/{folder_id}", response_model=FolderResponse)
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

@router.get("/scripts", response_model=List[ScriptResponse])
async def list_scripts(folder_id: Optional[int] = None):
    """获取所有脚本，或按目录筛选"""
    if folder_id:
        query = """
            SELECT * FROM workflow_scripts
            WHERE folder_id = %s
            ORDER BY id ASC
        """
        return mysql_service.execute_query(query, (folder_id,))
    else:
        query = "SELECT * FROM workflow_scripts ORDER BY id ASC"
        return mysql_service.execute_query(query)


@router.get("/scripts/{script_id}", response_model=ScriptResponse)
async def get_script(script_id: int):
    """获取单个脚本详情"""
    result = mysql_service.execute_query(
        "SELECT * FROM workflow_scripts WHERE id = %s", (script_id,)
    )
    if not result:
        raise HTTPException(status_code=404, detail="脚本不存在")
    return result[0]


@router.post("/scripts", response_model=ScriptResponse)
async def create_script(data: ScriptCreate):
    """创建脚本"""
    query = """
        INSERT INTO workflow_scripts (name, folder_id, sql_content, schedule_cron, schedule_label)
        VALUES (%s, %s, %s, %s, %s)
    """
    script_id = mysql_service.execute_insert(
        query, (data.name, data.folder_id, data.sql_content, data.schedule_cron, data.schedule_label)
    )
    if script_id == 0:
        raise HTTPException(status_code=500, detail="创建脚本失败")
    
    result = mysql_service.execute_query(
        "SELECT * FROM workflow_scripts WHERE id = %s", (script_id,)
    )
    return result[0] if result else None


@router.put("/scripts/{script_id}", response_model=ScriptResponse)
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
    
    query = f"UPDATE workflow_scripts SET {', '.join(updates)} WHERE id = %s"
    params.append(script_id)
    
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
async def run_script(script_id: int):
    """运行脚本（模拟）"""
    # 更新状态为运行中
    mysql_service.execute_update(
        "UPDATE workflow_scripts SET status = 'running' WHERE id = %s",
        (script_id,)
    )
    
    # 添加运行日志
    now = datetime.now()
    mysql_service.execute_insert(
        """INSERT INTO workflow_logs (script_id, status, start_time)
           VALUES (%s, 'running', %s)""",
        (script_id, now)
    )
    
    return {"message": "脚本已启动运行", "script_id": script_id}


# ==================== 日志接口 ====================

@router.get("/logs", response_model=List[LogResponse])
async def list_logs(script_id: Optional[int] = None, limit: int = 50):
    """获取运行日志"""
    if script_id:
        query = """
            SELECT * FROM workflow_logs
            WHERE script_id = %s
            ORDER BY start_time DESC
            LIMIT %s
        """
        return mysql_service.execute_query(query, (script_id, limit))
    else:
        query = """
            SELECT * FROM workflow_logs
            ORDER BY start_time DESC
            LIMIT %s
        """
        return mysql_service.execute_query(query, (limit,))
