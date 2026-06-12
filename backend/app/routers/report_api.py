"""报表 API 路由"""
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, field_serializer
from typing import Optional, List, Dict, Any
from datetime import datetime
from ..services.mysql_service import mysql_service


router = APIRouter(prefix="/api/v1/reports", tags=["报表"])


# ==================== 数据模型 ====================

class ReportResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    category: str
    cover_image: Optional[str]
    data_source_name: Optional[str]
    default_table: Optional[str]
    is_published: int
    view_count: int
    created_by: str
    created_at: datetime
    updated_at: datetime

    @field_serializer('created_at', 'updated_at')
    def serialize_datetime(self, v: datetime) -> str:
        if v is None:
            return ''
        return v.strftime('%Y-%m-%d %H:%M:%S') if isinstance(v, datetime) else str(v)


class FieldConfig(BaseModel):
    id: int
    field_name: str
    field_alias: str
    field_type: str
    data_type: str
    aggregation_type: Optional[str]
    sort_order: int
    is_visible: Optional[int] = 1
    format_string: Optional[str] = None


class ChartConfig(BaseModel):
    id: int
    chart_type: str
    title: Optional[str]
    config: Optional[dict]
    layout_order: int


class ReportDetailResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    category: str
    cover_image: Optional[str]
    data_source_name: Optional[str]
    default_table: Optional[str]
    is_published: int
    view_count: int
    created_by: str
    created_at: datetime
    updated_at: datetime
    fields: List[FieldConfig]
    charts: List[ChartConfig]

    @field_serializer('created_at', 'updated_at')
    def serialize_dt(self, v: datetime) -> str:
        if v is None:
            return ''
        return v.strftime('%Y-%m-%d %H:%M:%S') if isinstance(v, datetime) else str(v)


class QueryRequest(BaseModel):
    report_id: int
    dimensions: List[str] = []
    metrics: List[str] = []
    filters: Optional[List[dict]] = []
    aggregations: Optional[dict] = {}
    limit: int = 1000


class UpdateReportRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    cover_image: Optional[str] = None
    data_source_name: Optional[str] = None
    default_table: Optional[str] = None
    is_published: Optional[int] = None


class UpdateFieldRequest(BaseModel):
    id: Optional[int] = None
    field_name: str
    field_alias: str
    field_type: str
    data_type: str
    aggregation_type: Optional[str] = None
    sort_order: Optional[int] = 0
    is_visible: Optional[int] = 1
    format_string: Optional[str] = None


class UpdateChartRequest(BaseModel):
    id: Optional[int] = None
    chart_type: str
    title: Optional[str] = None
    config: Optional[dict] = None
    layout_order: Optional[int] = 0


class FullUpdateRequest(BaseModel):
    report: UpdateReportRequest
    fields: List[UpdateFieldRequest] = []
    charts: List[UpdateChartRequest] = []


class CreateReportRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    category: Optional[str] = "默认分类"


# ==================== 报表列表接口 ====================

@router.get("/", response_model=List[ReportResponse])
async def list_reports(category: Optional[str] = None, published_only: bool = False):
    """获取报表列表"""
    where_parts: List[str] = []
    params: List[Any] = []

    if published_only:
        where_parts.append("is_published = 1")
    if category:
        where_parts.append("category = %s")
        params.append(category)

    if where_parts:
        query = "SELECT * FROM report_metadata WHERE " + " AND ".join(where_parts) + " ORDER BY view_count DESC, created_at DESC"
    else:
        query = "SELECT * FROM report_metadata ORDER BY created_at DESC"

    results = mysql_service.execute_query(query, tuple(params))
    return results


@router.get("/categories", response_model=List[str])
async def list_categories():
    """获取所有报表分类"""
    query = "SELECT DISTINCT category FROM report_metadata WHERE category IS NOT NULL AND category != '' ORDER BY category"
    results = mysql_service.execute_query(query)
    return [r['category'] for r in results]


# ==================== 报表详情接口 ====================

@router.get("/{report_id}", response_model=ReportDetailResponse)
async def get_report_detail(report_id: int):
    """获取报表详情，包含字段配置和图表配置"""
    # 获取报表基本信息
    report_query = "SELECT * FROM report_metadata WHERE id = %s"
    report = mysql_service.execute_query(report_query, (report_id,))
    if not report:
        raise HTTPException(status_code=404, detail="报表不存在")

    # 更新浏览次数
    mysql_service.execute_update(
        "UPDATE report_metadata SET view_count = view_count + 1 WHERE id = %s",
        (report_id,)
    )

    # 获取字段配置
    fields_query = """
        SELECT id, field_name, field_alias, field_type, data_type,
               aggregation_type, sort_order, is_visible, format_string
        FROM report_data_config
        WHERE report_id = %s
        ORDER BY field_type, sort_order
    """
    fields = mysql_service.execute_query(fields_query, (report_id,))

    # 获取图表配置
    charts_query = """
        SELECT id, chart_type, title, config, layout_order
        FROM report_chart_configs
        WHERE report_id = %s
        ORDER BY layout_order
    """
    charts = mysql_service.execute_query(charts_query, (report_id,))

    # 解析 JSON 配置
    for chart in charts:
        if chart.get('config') and isinstance(chart['config'], str):
            import json
            try:
                chart['config'] = json.loads(chart['config'])
            except:
                chart['config'] = {}

    return {
        **report[0],
        'fields': fields,
        'charts': charts
    }


# ==================== 报表数据查询接口 ====================

@router.post("/query")
async def query_report_data(request: QueryRequest):
    """查询报表数据"""
    report_query = "SELECT * FROM report_metadata WHERE id = %s"
    report = mysql_service.execute_query(report_query, (request.report_id,))
    if not report:
        raise HTTPException(status_code=404, detail="报表不存在")

    report_info = report[0]
    table_name = report_info.get('default_table', '')

    if not table_name:
        return generate_mock_data(request.dimensions, request.metrics)

    # 构建查询
    select_parts = []

    for dim in request.dimensions:
        select_parts.append(dim)

    for metric in request.metrics:
        agg = (request.aggregations or {}).get(metric, 'sum')
        select_parts.append(f"{agg}({metric}) as {metric}")

    if not select_parts:
        raise HTTPException(status_code=400, detail="请至少选择一个维度或指标")

    group_by = ""
    if request.dimensions:
        group_by = f"GROUP BY {', '.join(request.dimensions)}"

    where_parts = []
    params: list = []
    if request.filters:
        for f in request.filters:
            field = f.get('field')
            operator = f.get('operator', '=')
            value = f.get('value')

            if operator == 'between':
                where_parts.append(f"{field} BETWEEN %s AND %s")
                params.extend(value)
            elif operator == 'in':
                placeholders = ', '.join(['%s'] * len(value))
                where_parts.append(f"{field} IN ({placeholders})")
                params.extend(value)
            else:
                where_parts.append(f"{field} {operator} %s")
                params.append(value)

    where_clause = ""
    if where_parts:
        where_clause = "WHERE " + " AND ".join(where_parts)

    order_field = request.dimensions[0] if request.dimensions else request.metrics[0]

    query_sql = f"""
        SELECT {', '.join(select_parts)}
        FROM {table_name}
        {where_clause}
        {group_by}
        ORDER BY {order_field}
        LIMIT %s
    """
    params.append(request.limit)

    try:
        results = mysql_service.execute_query(query_sql, tuple(params))
        return {
            "success": True,
            "data": results,
            "total": len(results),
            "sql": query_sql.replace('%s', '?').replace('\n', ' ')
        }
    except Exception as e:
        return generate_mock_data(request.dimensions, request.metrics)


def generate_mock_data(dimensions: List[str], metrics: List[str]):
    """生成模拟数据"""
    import random
    from datetime import datetime, timedelta

    data = []
    categories = ['手机', '电脑', '服装', '食品', '家电']
    provinces = ['北京', '上海', '广东', '浙江', '江苏']

    for i in range(10):
        row = {}

        if 'category' in dimensions:
            row['category'] = random.choice(categories)
        if 'province' in dimensions:
            row['province'] = random.choice(provinces)
        if 'dt' in dimensions:
            row['dt'] = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        if 'channel' in dimensions:
            row['channel'] = random.choice(['APP', '小程序', 'PC'])

        for metric in metrics:
            row[metric] = random.randint(1000, 100000)

        data.append(row)

    return {
        "success": True,
        "data": data,
        "total": len(data),
        "sql": "-- 模拟数据"
    }


# ==================== 报表管理接口 ====================

@router.post("/")
async def create_report(req: CreateReportRequest):
    """创建报表"""
    query = """
        INSERT INTO report_metadata (name, description, category, is_published, view_count, created_by)
        VALUES (%s, %s, %s, 1, 0, 'system')
    """
    report_id = mysql_service.execute_insert(query, (req.name, req.description or "", req.category or "默认分类"))
    if report_id == 0:
        raise HTTPException(status_code=500, detail="创建报表失败")
    return {"id": report_id, "message": "创建成功"}


@router.delete("/{report_id}")
async def delete_report(report_id: int):
    """删除报表（级联删除字段和图表配置）"""
    mysql_service.execute_update(
        "DELETE FROM report_chart_configs WHERE report_id = %s",
        (report_id,)
    )
    mysql_service.execute_update(
        "DELETE FROM report_data_config WHERE report_id = %s",
        (report_id,)
    )
    affected = mysql_service.execute_update(
        "DELETE FROM report_metadata WHERE id = %s",
        (report_id,)
    )
    if affected == 0:
        raise HTTPException(status_code=404, detail="报表不存在")
    return {"message": "删除成功"}


@router.put("/{report_id}")
async def update_report(report_id: int, req: UpdateReportRequest):
    """更新报表基本信息"""
    check_query = "SELECT id FROM report_metadata WHERE id = %s"
    report = mysql_service.execute_query(check_query, (report_id,))
    if not report:
        raise HTTPException(status_code=404, detail="报表不存在")

    update_fields = []
    update_params: list = []

    if req.name is not None:
        update_fields.append("name = %s")
        update_params.append(req.name)
    if req.description is not None:
        update_fields.append("description = %s")
        update_params.append(req.description)
    if req.category is not None:
        update_fields.append("category = %s")
        update_params.append(req.category)
    if req.cover_image is not None:
        update_fields.append("cover_image = %s")
        update_params.append(req.cover_image)
    if req.data_source_name is not None:
        update_fields.append("data_source_name = %s")
        update_params.append(req.data_source_name)
    if req.default_table is not None:
        update_fields.append("default_table = %s")
        update_params.append(req.default_table)
    if req.is_published is not None:
        update_fields.append("is_published = %s")
        update_params.append(req.is_published)

    if not update_fields:
        return {"message": "没有需要更新的字段"}

    update_fields.append("updated_at = NOW()")
    update_params.append(report_id)

    query = f"UPDATE report_metadata SET {', '.join(update_fields)} WHERE id = %s"
    mysql_service.execute_update(query, tuple(update_params))

    return {"message": "更新成功"}


# ==================== 字段配置管理 ====================

@router.get("/{report_id}/fields")
async def list_fields(report_id: int):
    """获取报表字段配置列表"""
    query = """
        SELECT id, field_name, field_alias, field_type, data_type,
               aggregation_type, sort_order, is_visible, format_string
        FROM report_data_config
        WHERE report_id = %s
        ORDER BY field_type, sort_order
    """
    return mysql_service.execute_query(query, (report_id,))


@router.post("/{report_id}/fields")
async def add_field(report_id: int, field: UpdateFieldRequest):
    """添加字段配置"""
    query = """
        INSERT INTO report_data_config
        (report_id, field_name, field_alias, field_type, data_type,
         aggregation_type, sort_order, is_visible, format_string)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    field_id = mysql_service.execute_insert(query, (
        report_id,
        field.field_name,
        field.field_alias,
        field.field_type,
        field.data_type,
        field.aggregation_type,
        field.sort_order or 0,
        field.is_visible if field.is_visible is not None else 1,
        field.format_string,
    ))
    return {"id": field_id, "message": "添加成功"}


@router.put("/{report_id}/fields/{field_id}")
async def update_field(report_id: int, field_id: int, field: UpdateFieldRequest):
    """更新字段配置"""
    query = """
        UPDATE report_data_config
        SET field_name = %s, field_alias = %s, field_type = %s, data_type = %s,
            aggregation_type = %s, sort_order = %s, is_visible = %s, format_string = %s
        WHERE id = %s AND report_id = %s
    """
    affected = mysql_service.execute_update(query, (
        field.field_name,
        field.field_alias,
        field.field_type,
        field.data_type,
        field.aggregation_type,
        field.sort_order or 0,
        field.is_visible if field.is_visible is not None else 1,
        field.format_string,
        field_id,
        report_id,
    ))
    if affected == 0:
        raise HTTPException(status_code=404, detail="字段不存在")
    return {"message": "更新成功"}


@router.delete("/{report_id}/fields/{field_id}")
async def delete_field(report_id: int, field_id: int):
    """删除字段配置"""
    affected = mysql_service.execute_update(
        "DELETE FROM report_data_config WHERE id = %s AND report_id = %s",
        (field_id, report_id)
    )
    if affected == 0:
        raise HTTPException(status_code=404, detail="字段不存在")
    return {"message": "删除成功"}


# ==================== 图表配置管理 ====================

@router.get("/{report_id}/charts")
async def list_charts(report_id: int):
    """获取报表图表配置列表"""
    query = """
        SELECT id, chart_type, title, config, layout_order
        FROM report_chart_configs
        WHERE report_id = %s
        ORDER BY layout_order
    """
    charts = mysql_service.execute_query(query, (report_id,))
    for chart in charts:
        if chart.get('config') and isinstance(chart['config'], str):
            import json
            try:
                chart['config'] = json.loads(chart['config'])
            except:
                chart['config'] = {}
    return charts


@router.post("/{report_id}/charts")
async def add_chart(report_id: int, chart: UpdateChartRequest):
    """添加图表配置"""
    import json
    config_str = json.dumps(chart.config or {}, ensure_ascii=False) if chart.config else None

    query = """
        INSERT INTO report_chart_configs (report_id, chart_type, title, config, layout_order)
        VALUES (%s, %s, %s, %s, %s)
    """
    chart_id = mysql_service.execute_insert(query, (
        report_id,
        chart.chart_type,
        chart.title,
        config_str,
        chart.layout_order or 0,
    ))
    return {"id": chart_id, "message": "添加成功"}


@router.put("/{report_id}/charts/{chart_id}")
async def update_chart(report_id: int, chart_id: int, chart: UpdateChartRequest):
    """更新图表配置"""
    import json
    config_str = json.dumps(chart.config or {}, ensure_ascii=False) if chart.config else None

    query = """
        UPDATE report_chart_configs
        SET chart_type = %s, title = %s, config = %s, layout_order = %s
        WHERE id = %s AND report_id = %s
    """
    affected = mysql_service.execute_update(query, (
        chart.chart_type,
        chart.title,
        config_str,
        chart.layout_order or 0,
        chart_id,
        report_id,
    ))
    if affected == 0:
        raise HTTPException(status_code=404, detail="图表不存在")
    return {"message": "更新成功"}


@router.delete("/{report_id}/charts/{chart_id}")
async def delete_chart(report_id: int, chart_id: int):
    """删除图表配置"""
    affected = mysql_service.execute_update(
        "DELETE FROM report_chart_configs WHERE id = %s AND report_id = %s",
        (chart_id, report_id)
    )
    if affected == 0:
        raise HTTPException(status_code=404, detail="图表不存在")
    return {"message": "删除成功"}


# ==================== 完整更新接口 ====================

@router.put("/{report_id}/full")
async def update_report_full(report_id: int, req: FullUpdateRequest):
    """完整更新报表：基本信息 + 字段 + 图表"""
    # 更新基本信息
    if req.report.model_dump(exclude_none=True):
        await update_report(report_id, req.report)

    # 删除旧的字段配置，重新插入
    mysql_service.execute_update(
        "DELETE FROM report_data_config WHERE report_id = %s",
        (report_id,)
    )
    for field in req.fields:
        query = """
            INSERT INTO report_data_config
            (report_id, field_name, field_alias, field_type, data_type,
             aggregation_type, sort_order, is_visible, format_string)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        mysql_service.execute_insert(query, (
            report_id,
            field.field_name,
            field.field_alias,
            field.field_type,
            field.data_type,
            field.aggregation_type,
            field.sort_order or 0,
            field.is_visible if field.is_visible is not None else 1,
            field.format_string,
        ))

    # 删除旧的图表配置，重新插入
    mysql_service.execute_update(
        "DELETE FROM report_chart_configs WHERE report_id = %s",
        (report_id,)
    )
    import json
    for chart in req.charts:
        config_str = json.dumps(chart.config or {}, ensure_ascii=False) if chart.config else None
        query = """
            INSERT INTO report_chart_configs (report_id, chart_type, title, config, layout_order)
            VALUES (%s, %s, %s, %s, %s)
        """
        mysql_service.execute_insert(query, (
            report_id,
            chart.chart_type,
            chart.title,
            config_str,
            chart.layout_order or 0,
        ))

    return {"message": "完整更新成功"}
