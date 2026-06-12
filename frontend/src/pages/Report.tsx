import { useState, useEffect, useRef } from 'react'
import { Card, Input, Button, Row, Col, Select, Space, Typography, Spin, message, Table, Tag, Empty, Tabs, Badge, Modal, Form, InputNumber, Radio, Divider, List } from 'antd'
import { SearchOutlined, BarChartOutlined, TableOutlined, ArrowLeftOutlined, ReloadOutlined, PlusOutlined, DeleteOutlined, EditOutlined, SaveOutlined, SettingOutlined } from '@ant-design/icons'
import api from '../services/api'

const { Title, Text } = Typography
const { Search } = Input

interface FieldItem {
  id: number
  field_name: string
  field_alias: string
  field_type: 'dimension' | 'metric'
  data_type: string
  aggregation_type?: string
  sort_order?: number
  is_visible?: number
  format_string?: string
}

interface ChartItem {
  id: number
  chart_type: string
  title?: string
  config?: any
  layout_order?: number
}

interface ReportCard {
  id: number
  name: string
  description: string
  category: string
  view_count: number
  created_at: string
}

interface ReportDetail {
  id: number
  name: string
  description?: string
  category: string
  cover_image?: string
  data_source_name?: string
  default_table?: string
  is_published: number
  view_count: number
  created_by: string
  created_at: string
  updated_at: string
  fields: FieldItem[]
  charts: ChartItem[]
}

const chartTypeMap: Record<string, string> = {
  column: '柱状图',
  line: '折线图',
  pie: '饼图',
  bar: '条形图',
  table: '表格',
  area: '面积图',
}

const aggregationOptions = [
  { label: '求和 (sum)', value: 'sum' },
  { label: '平均 (avg)', value: 'avg' },
  { label: '计数 (count)', value: 'count' },
  { label: '最大 (max)', value: 'max' },
  { label: '最小 (min)', value: 'min' },
]

const Report = () => {
  const [loading, setLoading] = useState(false)
  const [reports, setReports] = useState<ReportCard[]>([])
  const [categories, setCategories] = useState<string[]>([])
  const [selectedCategory, setSelectedCategory] = useState<string>('')
  const [searchText, setSearchText] = useState('')
  const [selectedReport, setSelectedReport] = useState<number | null>(null)
  const [reportDetail, setReportDetail] = useState<ReportDetail | null>(null)
  const [dimensions, setDimensions] = useState<FieldItem[]>([])
  const [metrics, setMetrics] = useState<FieldItem[]>([])
  const [selectedDimensions, setSelectedDimensions] = useState<string[]>([])
  const [selectedMetrics, setSelectedMetrics] = useState<string[]>([])
  const [aggregations, setAggregations] = useState<Record<string, string>>({})
  const [queryResult, setQueryResult] = useState<any>(null)
  const [queryLoading, setQueryLoading] = useState(false)

  // ClickHouse 相关
  const [useClickHouse, setUseClickHouse] = useState(false)
  const [chDatabases, setChDatabases] = useState<string[]>([])
  const [selectedChDb, setSelectedChDb] = useState<string>('')
  const [chTables, setChTables] = useState<{name: string, database: string}[]>([])
  const [selectedChTable, setSelectedChTable] = useState<string>('')
  const [tableSchema, setTableSchema] = useState<any[]>([])

  // 新建报表
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [newReport, setNewReport] = useState({ name: '', description: '', category: '' })

  // 编辑报表
  const [showEditModal, setShowEditModal] = useState(false)
  const [editReport, setEditReport] = useState<{
    id: number | null
    name: string
    description: string
    category: string
    cover_image: string
    data_source_name: string
    default_table: string
    is_published: number
    fields: FieldItem[]
    charts: ChartItem[]
  }>({
    id: null, name: '', description: '', category: '',
    cover_image: '', data_source_name: '', default_table: '',
    is_published: 1, fields: [], charts: [],
  })
  const [savingEdit, setSavingEdit] = useState(false)
  const [activeTab, setActiveTab] = useState('basic')

  // 加载报表列表
  const loadReports = async () => {
    setLoading(true)
    try {
      const [reportsRes, categoriesRes] = await Promise.all([
        api.get('/reports/', { params: { category: selectedCategory || undefined } }),
        api.get('/reports/categories'),
      ])
      setReports(reportsRes.data)
      setCategories(categoriesRes.data)
    } catch (error: any) {
      message.error(error.response?.data?.detail || '加载报表失败')
    } finally {
      setLoading(false)
    }
  }

  // 加载 ClickHouse
  const loadClickHouse = async () => {
    try {
      const res = await api.get('/clickhouse/databases')
      setChDatabases(res.data || [])
    } catch (e) {
      // 不报错，只是没连上
    }
  }

  useEffect(() => {
    loadReports()
    loadClickHouse()
  }, [selectedCategory])

  useEffect(() => {
    if (!selectedChDb) return
    api.get('/clickhouse/tables', { params: { database: selectedChDb } })
      .then(res => setChTables(res.data || []))
      .catch(() => {})
  }, [selectedChDb])

  useEffect(() => {
    if (!selectedChTable) return
    api.get(`/clickhouse/tables/${selectedChTable}/schema`, { params: { database: selectedChDb } })
      .then(res => {
        setTableSchema(res.data || [])
      })
      .catch(() => {})
  }, [selectedChTable, selectedChDb])

  const loadReportDetail = async (reportId: number) => {
    setLoading(true)
    setSelectedReport(reportId)
    try {
      const res = await api.get(`/reports/${reportId}`)
      const data: ReportDetail = res.data
      setReportDetail(data)
      const dims = data.fields.filter(f => f.field_type === 'dimension')
      const mets = data.fields.filter(f => f.field_type === 'metric')
      setDimensions(dims)
      setMetrics(mets)
      setSelectedDimensions(dims.slice(0, 1).map(d => d.field_name))
      setSelectedMetrics(mets.slice(0, 1).map(m => m.field_name))
      const defaultAggs: Record<string, string> = {}
      mets.forEach(m => { defaultAggs[m.field_name] = m.aggregation_type || 'sum' })
      setAggregations(defaultAggs)

      // 自动设置 ClickHouse 数据源
      if (data.data_source_name?.toLowerCase().includes('clickhouse') && data.default_table) {
        setUseClickHouse(true)
        // 从 default_table 中解析数据库和表名，格式为 db.table
        const tableParts = data.default_table.split('.')
        if (tableParts.length >= 2) {
          setSelectedChDb(tableParts[0])
          setSelectedChTable(tableParts.slice(1).join('.'))
        } else {
          setSelectedChDb('default')
          setSelectedChTable(data.default_table)
        }
      } else {
        setUseClickHouse(false)
      }
    } catch (error: any) {
      message.error(error.response?.data?.detail || '加载报表详情失败')
    } finally {
      setLoading(false)
    }
  }

  // 查询数据
  const handleQuery = async () => {
    if (selectedDimensions.length === 0 && selectedMetrics.length === 0) {
      message.warning('请至少选择一个维度或指标')
      return
    }
    setQueryLoading(true)
    try {
      if (useClickHouse && selectedChTable) {
        const groupBy = selectedDimensions.length > 0 ? `GROUP BY ${selectedDimensions.join(', ')}` : ''
        const selectParts = [
          ...selectedDimensions,
          ...selectedMetrics.map(m => `${aggregations[m] || 'sum'}(${m}) as ${m}`),
        ]
        const sql = `SELECT ${selectParts.join(', ')} FROM ${selectedChDb}.${selectedChTable} ${groupBy} LIMIT 1000`
        const response = await api.post('/clickhouse/query', { sql })
        // 按维度升序排序
        const rawData = response.data.data || []
        const sortedData = [...rawData].sort((a: any, b: any) => {
          for (const dim of selectedDimensions) {
            const aVal = String(a[dim] ?? '')
            const bVal = String(b[dim] ?? '')
            const cmp = aVal.localeCompare(bVal, 'zh-CN', { numeric: true })
            if (cmp !== 0) return cmp
          }
          return 0
        })
        setQueryResult({
          success: true,
          data: sortedData,
          total: response.data.total,
          sql,
        })
      } else {
        const response = await api.post('/reports/query', {
          report_id: selectedReport,
          dimensions: selectedDimensions,
          metrics: selectedMetrics,
          aggregations: aggregations,
          limit: 1000,
        })
        const rawData = response.data.data || []
        const sortedData = [...rawData].sort((a: any, b: any) => {
          for (const dim of selectedDimensions) {
            const aVal = String(a[dim] ?? '')
            const bVal = String(b[dim] ?? '')
            const cmp = aVal.localeCompare(bVal, 'zh-CN', { numeric: true })
            if (cmp !== 0) return cmp
          }
          return 0
        })
        setQueryResult({ ...response.data, data: sortedData })
      }
      message.success('查询成功')
    } catch (error: any) {
      message.error(error.response?.data?.detail || '查询失败')
    } finally {
      setQueryLoading(false)
    }
  }

  // 创建报表
  const handleCreateReport = async () => {
    if (!newReport.name) { message.warning('请输入报表名称'); return }
    try {
      await api.post('/reports/', newReport)
      message.success('创建成功')
      setShowCreateModal(false)
      setNewReport({ name: '', description: '', category: '' })
      loadReports()
    } catch (error: any) {
      message.error(error.response?.data?.detail || '创建失败')
    }
  }

  // 删除报表
  const handleDeleteReport = async (reportId: number) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除这个报表吗？相关字段配置和图表配置也将被删除。',
      okText: '删除',
      okType: 'danger',
      onOk: async () => {
        try {
          await api.delete(`/reports/${reportId}`)
          message.success('删除成功')
          loadReports()
          if (selectedReport === reportId) {
            setSelectedReport(null)
            setReportDetail(null)
          }
        } catch (error: any) {
          message.error(error.response?.data?.detail || '删除失败')
        }
      },
    })
  }

  // ================ 编辑报表 ================

  const openEditModal = (report: ReportDetail) => {
    setEditReport({
      id: report.id,
      name: report.name,
      description: report.description || '',
      category: report.category || '',
      cover_image: report.cover_image || '',
      data_source_name: report.data_source_name || '',
      default_table: report.default_table || '',
      is_published: report.is_published,
      fields: JSON.parse(JSON.stringify(report.fields || [])),
      charts: JSON.parse(JSON.stringify(report.charts || [])),
    })
    setActiveTab('basic')
    setShowEditModal(true)
  }

  const addField = (type: 'dimension' | 'metric') => {
    const newField: FieldItem = {
      id: -Date.now(),
      field_name: '',
      field_alias: '',
      field_type: type,
      data_type: type === 'dimension' ? 'string' : 'number',
      aggregation_type: type === 'metric' ? 'sum' : undefined,
      sort_order: editReport.fields.length,
      is_visible: 1,
    }
    setEditReport({ ...editReport, fields: [...editReport.fields, newField] })
  }

  const updateField = (idx: number, patch: Partial<FieldItem>) => {
    const fields = [...editReport.fields]
    fields[idx] = { ...fields[idx], ...patch }
    setEditReport({ ...editReport, fields })
  }

  const removeField = (idx: number) => {
    const fields = editReport.fields.filter((_, i) => i !== idx)
    setEditReport({ ...editReport, fields })
  }

  const addChart = () => {
    const newChart: ChartItem = {
      id: -Date.now(),
      chart_type: 'column',
      title: '',
      config: {},
      layout_order: editReport.charts.length,
    }
    setEditReport({ ...editReport, charts: [...editReport.charts, newChart] })
  }

  const updateChart = (chartId: number | string, patch: Partial<ChartItem>) => {
    const charts = editReport.charts.map(c => 
      c.id === chartId ? { ...c, ...patch } : c
    )
    setEditReport({ ...editReport, charts })
  }

  const removeChart = (chartId: number | string) => {
    const charts = editReport.charts.filter(c => c.id !== chartId)
    setEditReport({ ...editReport, charts })
  }

  const handleSaveEdit = async () => {
    if (!editReport.name?.trim()) { message.warning('请输入报表名称'); return }

    // 校验字段
    for (let i = 0; i < editReport.fields.length; i++) {
      const f = editReport.fields[i]
      if (!f.field_name.trim()) { message.warning(`第 ${i + 1} 个字段的字段名不能为空`); return }
      if (!f.field_alias.trim()) { message.warning(`第 ${i + 1} 个字段的显示名不能为空`); return }
    }
    for (let i = 0; i < editReport.charts.length; i++) {
      const c = editReport.charts[i]
      if (!c.chart_type) { message.warning(`第 ${i + 1} 个图表的类型不能为空`); return }
    }

    setSavingEdit(true)
    try {
      await api.put(`/reports/${editReport.id}/full`, {
        report: {
          name: editReport.name,
          description: editReport.description,
          category: editReport.category,
          cover_image: editReport.cover_image,
          data_source_name: editReport.data_source_name,
          default_table: editReport.default_table,
          is_published: editReport.is_published,
        },
        fields: editReport.fields.map(f => ({
          id: f.id > 0 ? f.id : undefined,
          field_name: f.field_name,
          field_alias: f.field_alias,
          field_type: f.field_type,
          data_type: f.data_type,
          aggregation_type: f.aggregation_type,
          sort_order: f.sort_order || 0,
          is_visible: f.is_visible ?? 1,
          format_string: f.format_string,
        })),
        charts: editReport.charts.map(c => ({
          id: c.id > 0 ? c.id : undefined,
          chart_type: c.chart_type,
          title: c.title,
          config: c.config || {},
          layout_order: c.layout_order || 0,
        })),
      })
      message.success('保存成功')
      setShowEditModal(false)
      if (selectedReport === editReport.id && editReport.id !== null) {
        loadReportDetail(editReport.id)
      }
      loadReports()
    } catch (error: any) {
      message.error(error.response?.data?.detail || '保存失败')
    } finally {
      setSavingEdit(false)
    }
  }

  // ================ 渲染 ================

  const renderReportList = () => (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
          <Search
            placeholder="搜索报表..."
            style={{ width: 300 }}
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
          />
          <Select
            placeholder="选择分类"
            style={{ width: 150 }}
            allowClear
            value={selectedCategory || undefined}
            onChange={(v) => setSelectedCategory(v || '')}
            options={categories.map(c => ({ value: c, label: c }))}
          />
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setShowCreateModal(true)}>
          新建报表
        </Button>
      </div>

      <Row gutter={[16, 16]}>
        {reports
          .filter(r => !searchText || r.name.includes(searchText) || (r.description || '').includes(searchText))
          .map(report => (
            <Col xs={24} sm={12} lg={8} key={report.id}>
              <Card
                hoverable
                onClick={() => loadReportDetail(report.id)}
                cover={
                  <div style={{
                    height: 120,
                    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>
                    <BarChartOutlined style={{ fontSize: 48, color: 'white' }} />
                  </div>
                }
                actions={[
                  <Text key="view" type="secondary">浏览 {report.view_count}</Text>,
                  <Button key="edit" icon={<EditOutlined />} size="small" onClick={(e) => {
                    e.stopPropagation()
                    // 点击编辑时先加载详情，再打开编辑
                    if (reportDetail && reportDetail.id === report.id) {
                      openEditModal(reportDetail)
                    } else {
                      api.get(`/reports/${report.id}`).then(res => {
                        openEditModal(res.data)
                      }).catch(() => {
                        message.error('加载失败')
                      })
                    }
                  }} />,
                  <Button key="delete" icon={<DeleteOutlined />} size="small" danger onClick={(e) => { e.stopPropagation(); handleDeleteReport(report.id) }} />,
                ]}
              >
                <Card.Meta
                  title={report.name}
                  description={
                    <div>
                      <Text type="secondary" ellipsis={{ tooltip: true }}>{report.description}</Text>
                      <div style={{ marginTop: 8 }}>
                        <Tag color="blue">{report.category}</Tag>
                      </div>
                    </div>
                  }
                />
              </Card>
            </Col>
          ))}
      </Row>
      {reports.length === 0 && <Empty description="暂无报表" style={{ marginTop: 60 }} />}
    </div>
  )

  const renderDataExplorer = () => (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => { setSelectedReport(null); setReportDetail(null); setQueryResult(null) }}>
          返回列表
        </Button>
        <Title level={4} style={{ margin: 0 }}>{reportDetail?.name}</Title>
        <Space>
          <Button icon={<EditOutlined />} onClick={() => reportDetail && openEditModal(reportDetail)}>编辑</Button>
          <Button type="primary" icon={<SearchOutlined />} onClick={handleQuery} loading={queryLoading}>查询数据</Button>
        </Space>
      </div>

      <Card size="small" title="数据源选择" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
          <span>数据源：</span>
          <Radio.Group value={useClickHouse ? 'ch' : 'mysql'} onChange={(e) => setUseClickHouse(e.target.value === 'ch')}>
            <Radio value="ch">实时数据 (ClickHouse)</Radio>
          </Radio.Group>
          {useClickHouse && (
            <Space style={{ marginLeft: 16 }}>
              <Select
                style={{ width: 160 }}
                placeholder="选择数据库"
                value={selectedChDb || undefined}
                onChange={(v) => { setSelectedChDb(v); setSelectedChTable('') }}
                options={chDatabases.map(db => ({ value: db, label: db }))}
              />
              <Select
                style={{ width: 200 }}
                placeholder="选择表"
                value={selectedChTable || undefined}
                onChange={(v) => setSelectedChTable(v)}
                options={chTables.map(t => ({ value: t.name, label: t.name }))}
              />
            </Space>
          )}
        </div>
        {useClickHouse && selectedChTable && tableSchema.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <Text strong>表结构：</Text>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 8 }}>
              {tableSchema.map((f: any) => (
                <Tag key={f.name} color={String(f.type).toLowerCase().includes('int') || String(f.type).toLowerCase().includes('decimal') || String(f.type).toLowerCase().includes('float') ? 'green' : 'blue'}>
                  {f.name}: {f.type}
                </Tag>
              ))}
            </div>
          </div>
        )}
      </Card>

      <Row gutter={16}>
        <Col span={6}>
          <Card size="small" title="可用字段" style={{ marginBottom: 16 }}>
            <div style={{ marginBottom: 16 }}>
              <Text strong>维度</Text>
              <div style={{ marginTop: 8 }}>
                {dimensions.length === 0 && <Text type="secondary" style={{ fontSize: 12 }}>（暂无维度字段）</Text>}
                {dimensions.map(dim => (
                  <Tag
                    key={dim.id}
                    color={selectedDimensions.includes(dim.field_name) ? 'blue' : 'default'}
                    style={{ marginBottom: 4, cursor: 'pointer' }}
                    onClick={() => {
                      if (selectedDimensions.includes(dim.field_name)) {
                        setSelectedDimensions(selectedDimensions.filter(d => d !== dim.field_name))
                      } else {
                        setSelectedDimensions([...selectedDimensions, dim.field_name])
                      }
                    }}
                  >
                    {dim.field_alias || dim.field_name}
                  </Tag>
                ))}
              </div>
            </div>
            <div>
              <Text strong>指标</Text>
              <div style={{ marginTop: 8 }}>
                {metrics.length === 0 && <Text type="secondary" style={{ fontSize: 12 }}>（暂无指标字段）</Text>}
                {metrics.map(met => (
                  <Tag
                    key={met.id}
                    color={selectedMetrics.includes(met.field_name) ? 'green' : 'default'}
                    style={{ marginBottom: 4, cursor: 'pointer' }}
                    onClick={() => {
                      if (selectedMetrics.includes(met.field_name)) {
                        setSelectedMetrics(selectedMetrics.filter(m => m !== met.field_name))
                      } else {
                        setSelectedMetrics([...selectedMetrics, met.field_name])
                      }
                    }}
                  >
                    {met.field_alias || met.field_name}
                  </Tag>
                ))}
              </div>
            </div>
          </Card>
        </Col>

        <Col span={18}>
          <Card size="small" title="维度/指标配置" style={{ marginBottom: 16 }}>
            <Row gutter={16}>
              <Col span={12}>
                <div style={{
                  border: '2px dashed #d9d9d9',
                  borderRadius: 8,
                  padding: 16,
                  minHeight: 100,
                  background: selectedDimensions.length > 0 ? '#e6f7ff' : '#fafafa',
                }}>
                  <Text strong>已选维度</Text>
                  <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                    {selectedDimensions.map(dimName => {
                      const dim = dimensions.find(d => d.field_name === dimName)
                      return dim ? (
                        <Tag
                          key={dimName}
                          closable
                          onClose={() => setSelectedDimensions(selectedDimensions.filter(d => d !== dimName))}
                          color="blue"
                        >
                          {dim.field_alias || dim.field_name}
                        </Tag>
                      ) : null
                    })}
                    {selectedDimensions.length === 0 && <Text type="secondary">点击左侧选择维度</Text>}
                  </div>
                </div>
              </Col>
              <Col span={12}>
                <div style={{
                  border: '2px dashed #d9d9d9',
                  borderRadius: 8,
                  padding: 16,
                  minHeight: 100,
                  background: selectedMetrics.length > 0 ? '#f6ffed' : '#fafafa',
                }}>
                  <Text strong>已选指标</Text>
                  <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                    {selectedMetrics.map(metName => {
                      const met = metrics.find(m => m.field_name === metName)
                      return met ? (
                        <Tag
                          key={metName}
                          closable
                          onClose={() => setSelectedMetrics(selectedMetrics.filter(m => m !== metName))}
                          color="green"
                        >
                          {met.field_alias || met.field_name} ({aggregations[metName] || 'sum'})
                        </Tag>
                      ) : null
                    })}
                    {selectedMetrics.length === 0 && <Text type="secondary">点击左侧选择指标</Text>}
                  </div>
                </div>
              </Col>
            </Row>
          </Card>

          {selectedMetrics.length > 0 && (
            <Card size="small" title="聚合方式" style={{ marginBottom: 16 }}>
              <Space wrap>
                {selectedMetrics.map(metName => {
                  const met = metrics.find(m => m.field_name === metName)
                  return met ? (
                    <div key={metName} style={{ marginBottom: 8 }}>
                      <Text>{met.field_alias || met.field_name}：</Text>
                      <Select
                        size="small"
                        style={{ width: 110 }}
                        value={aggregations[metName] || 'sum'}
                        onChange={(v) => setAggregations({ ...aggregations, [metName]: v })}
                        options={aggregationOptions}
                      />
                    </div>
                  ) : null
                })}
              </Space>
            </Card>
          )}

          {queryResult && (
            <Card
              size="small"
              title={
                <Space>
                  <span>查询结果</span>
                  <Badge count={queryResult.total} style={{ backgroundColor: '#52c41a' }} />
                </Space>
              }
              extra={<Button size="small" icon={<ReloadOutlined />} onClick={handleQuery}>刷新</Button>}
            >
              {queryResult.sql && (
                <div style={{ marginBottom: 16 }}>
                  <Text strong>执行的 SQL：</Text>
                  <pre style={{
                    background: '#f5f5f5', padding: 8, borderRadius: 4,
                    fontFamily: 'Monaco, Consolas, monospace',
                    fontSize: 12, overflow: 'auto', margin: '8px 0 0 0',
                  }}>{queryResult.sql}</pre>
                </div>
              )}
              <Tabs
                defaultActiveKey="table"
                items={(() => {
                  // 获取报表配置的图表：只显示用户配置的图表类型；未配置时显示全部
                  const configuredCharts = reportDetail?.charts && reportDetail.charts.length > 0
                    ? [...reportDetail.charts].sort((a, b) => (a.layout_order || 0) - (b.layout_order || 0))
                    : null
                  const tableItem = {
                    key: 'table',
                    label: <span><TableOutlined /> 表格</span>,
                    children: queryResult.data && queryResult.data.length > 0 ? (
                      <Table
                        dataSource={queryResult.data}
                        rowKey={(_, index) => String(index)}
                        pagination={{ pageSize: 20 }}
                        size="small"
                        bordered
                        scroll={{ x: 'max-content' }}
                        columns={Object.keys(queryResult.data[0] || {}).map(key => ({
                          title: key,
                          dataIndex: key,
                          key: key,
                          width: 150,
                          ellipsis: true,
                          sorter: (a: any, b: any) => {
                            const aVal = a[key]
                            const bVal = b[key]
                            if (typeof aVal === 'number' && typeof bVal === 'number') {
                              return aVal - bVal
                            }
                            return String(aVal).localeCompare(String(bVal), 'zh-CN', { numeric: true })
                          },
                        }))}
                      />
                    ) : <Empty description="暂无数据" />,
                  }

                  if (!configuredCharts) {
                    // 未配置图表 - 显示所有图表类型（探索模式）
                    const allChartTabs = Object.keys(chartTypeMap).filter(k => k !== 'table').map(k => ({
                      key: k,
                      label: <span>{chartTypeMap[k]}</span>,
                      children: queryResult.data && queryResult.data.length > 0 ? (
                        <PlaceholderChart
                          chartType={k}
                          data={queryResult.data}
                          dimensionFields={selectedDimensions}
                          metricFields={selectedMetrics}
                        />
                      ) : <Empty />,
                    }))
                    return [tableItem, ...allChartTabs]
                  } else {
                    // 已配置图表 - 只显示配置的图表类型（排除 table，因为已单独显示）
                    const configuredTabs = configuredCharts
                      .filter(chart => chart.chart_type !== 'table')
                      .map((chart) => ({
                        key: String(chart.id),
                        label: <span>{chart.title || chartTypeMap[chart.chart_type] || chart.chart_type}</span>,
                        children: queryResult.data && queryResult.data.length > 0 ? (
                          <PlaceholderChart
                            chartType={chart.chart_type}
                            data={queryResult.data}
                            dimensionFields={selectedDimensions}
                            metricFields={selectedMetrics}
                          />
                        ) : <Empty />,
                      }))
                    return [tableItem, ...configuredTabs]
                  }
                })()}
              />
            </Card>
          )}
        </Col>
      </Row>
    </div>
  )

  return (
    <div style={{ height: 'calc(100vh - 48px)', overflow: 'auto' }}>
      <Title level={4}>报表中心</Title>
      <Text type="secondary">选择报表或创建新的数据分析视图</Text>

      <div style={{ marginTop: 16 }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: 60 }}><Spin size="large" /></div>
        ) : selectedReport ? (
          renderDataExplorer()
        ) : (
          renderReportList()
        )}
      </div>

      {/* 新建报表模态框 */}
      <Modal
        title="新建报表"
        open={showCreateModal}
        onCancel={() => setShowCreateModal(false)}
        footer={[
          <Button key="back" onClick={() => setShowCreateModal(false)}>取消</Button>,
          <Button key="submit" type="primary" onClick={handleCreateReport}>确认创建</Button>,
        ]}
      >
        <Form layout="vertical">
          <Form.Item label="报表名称">
            <Input value={newReport.name} onChange={(e) => setNewReport({ ...newReport, name: e.target.value })} placeholder="例如：销售数据概览" />
          </Form.Item>
          <Form.Item label="报表描述">
            <Input.TextArea value={newReport.description} onChange={(e) => setNewReport({ ...newReport, description: e.target.value })} placeholder="简短描述报表用途" rows={3} />
          </Form.Item>
          <Form.Item label="分类">
            <Select
              value={newReport.category || undefined}
              onChange={(v) => setNewReport({ ...newReport, category: v || '' })}
              options={categories.map(c => ({ value: c, label: c }))}
              placeholder="选择分类"
              allowClear
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* 编辑报表模态框 */}
      <Modal
        title={`编辑报表 - ${editReport.name}`}
        open={showEditModal}
        onCancel={() => setShowEditModal(false)}
        width={900}
        footer={[
          <Button key="back" onClick={() => setShowEditModal(false)}>取消</Button>,
          <Button key="submit" type="primary" icon={<SaveOutlined />} onClick={handleSaveEdit} loading={savingEdit}>
            保存
          </Button>,
        ]}
      >
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={[
            {
              key: 'basic',
              label: <span><SettingOutlined /> 基本信息</span>,
              children: (
                <Form layout="vertical" style={{ marginTop: 16 }}>
                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item label="报表名称"><Input value={editReport.name} onChange={(e) => setEditReport({ ...editReport, name: e.target.value })} placeholder="请输入名称" /></Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item label="分类">
                        <Select
                          value={editReport.category || undefined}
                          onChange={(v) => setEditReport({ ...editReport, category: v || '' })}
                          options={[...new Set([...categories, '销售分析', '用户分析', '运营分析', '财务分析', '供应链分析'])].map(c => ({ value: c, label: c }))}
                          placeholder="选择或输入分类"
                          allowClear
                        />
                      </Form.Item>
                    </Col>
                  </Row>
                  <Form.Item label="报表描述">
                    <Input.TextArea value={editReport.description} onChange={(e) => setEditReport({ ...editReport, description: e.target.value })} rows={3} placeholder="简短描述报表用途" />
                  </Form.Item>
                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item label="数据源名称"><Input value={editReport.data_source_name} onChange={(e) => setEditReport({ ...editReport, data_source_name: e.target.value })} placeholder="例如：ClickHouse / MySQL" /></Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item label="默认查询表"><Input value={editReport.default_table} onChange={(e) => setEditReport({ ...editReport, default_table: e.target.value })} placeholder="例如：dw_sales_summary" /></Form.Item>
                    </Col>
                  </Row>
                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item label="封面图 URL"><Input value={editReport.cover_image} onChange={(e) => setEditReport({ ...editReport, cover_image: e.target.value })} placeholder="可选" /></Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item label="是否发布">
                        <Radio.Group value={editReport.is_published} onChange={(e) => setEditReport({ ...editReport, is_published: e.target.value })}>
                          <Radio value={1}>已发布</Radio>
                          <Radio value={0}>草稿</Radio>
                        </Radio.Group>
                      </Form.Item>
                    </Col>
                  </Row>
                </Form>
              ),
            },
            {
              key: 'fields',
              label: <span><TableOutlined /> 字段配置 ({editReport.fields.length})</span>,
              children: (
                <div style={{ marginTop: 16 }}>
                  <Space style={{ marginBottom: 16 }}>
                    <Button icon={<PlusOutlined />} onClick={() => addField('dimension')}>新增维度</Button>
                    <Button icon={<PlusOutlined />} type="dashed" onClick={() => addField('metric')}>新增指标</Button>
                  </Space>
                  {editReport.fields.length === 0 ? (
                    <Empty description="暂无字段，点击上方按钮新增" />
                  ) : (
                    <>
                      <Divider style={{ margin: '8px 0' }}>维度字段</Divider>
                      {editReport.fields
                        .map((f, idx) => ({ f, idx }))
                        .filter(item => item.f.field_type === 'dimension')
                        .map(({ f, idx }) => (
                          <Row key={f.id} gutter={8} style={{ marginBottom: 8, alignItems: 'center' }}>
                            <Col span={5}><Input size="small" value={f.field_name} placeholder="字段名（英文）" onChange={(e) => updateField(idx, { field_name: e.target.value })} /></Col>
                            <Col span={5}><Input size="small" value={f.field_alias} placeholder="显示名（中文）" onChange={(e) => updateField(idx, { field_alias: e.target.value })} /></Col>
                            <Col span={4}><Select size="small" value={f.data_type} onChange={(v) => updateField(idx, { data_type: v })} options={[{value:'string'},{value:'date'},{value:'datetime'},{value:'number'}]} style={{ width: '100%' }} /></Col>
                            <Col span={3}><InputNumber size="small" value={f.sort_order || 0} onChange={(v) => updateField(idx, { sort_order: Number(v) || 0 })} style={{ width: '100%' }} placeholder="排序" /></Col>
                            <Col span={3}><Select size="small" value={f.is_visible ?? 1} onChange={(v) => updateField(idx, { is_visible: v })} options={[{value:1,label:'显示'},{value:0,label:'隐藏'}]} style={{ width: '100%' }} /></Col>
                            <Col span={3}><Input size="small" value={f.format_string || ''} placeholder="格式化（可选）" onChange={(e) => updateField(idx, { format_string: e.target.value })} /></Col>
                            <Col span={1} style={{ textAlign: 'center' }}><Button type="text" danger size="small" icon={<DeleteOutlined />} onClick={() => removeField(idx)} /></Col>
                          </Row>
                        ))}
                      <Divider style={{ margin: '16px 0 8px 0' }}>指标字段</Divider>
                      {editReport.fields
                        .map((f, idx) => ({ f, idx }))
                        .filter(item => item.f.field_type === 'metric')
                        .map(({ f, idx }) => (
                          <Row key={f.id} gutter={8} style={{ marginBottom: 8, alignItems: 'center' }}>
                            <Col span={5}><Input size="small" value={f.field_name} placeholder="字段名（英文）" onChange={(e) => updateField(idx, { field_name: e.target.value })} /></Col>
                            <Col span={5}><Input size="small" value={f.field_alias} placeholder="显示名（中文）" onChange={(e) => updateField(idx, { field_alias: e.target.value })} /></Col>
                            <Col span={4}><Select size="small" value={f.data_type} onChange={(v) => updateField(idx, { data_type: v })} options={[{value:'number'},{value:'int'},{value:'decimal'},{value:'float'},{value:'string'}]} style={{ width: '100%' }} /></Col>
                            <Col span={4}><Select size="small" value={f.aggregation_type || 'sum'} onChange={(v) => updateField(idx, { aggregation_type: v })} options={aggregationOptions} style={{ width: '100%' }} /></Col>
                            <Col span={3}><InputNumber size="small" value={f.sort_order || 0} onChange={(v) => updateField(idx, { sort_order: Number(v) || 0 })} style={{ width: '100%' }} placeholder="排序" /></Col>
                            <Col span={2}><Select size="small" value={f.is_visible ?? 1} onChange={(v) => updateField(idx, { is_visible: v })} options={[{value:1,label:'显示'},{value:0,label:'隐藏'}]} style={{ width: '100%' }} /></Col>
                            <Col span={1} style={{ textAlign: 'center' }}><Button type="text" danger size="small" icon={<DeleteOutlined />} onClick={() => removeField(idx)} /></Col>
                          </Row>
                        ))}
                    </>
                  )}
                </div>
              ),
            },
            {
              key: 'charts',
              label: <span><BarChartOutlined /> 图表配置 ({editReport.charts.length})</span>,
              children: (
                <div style={{ marginTop: 16 }}>
                  <Space style={{ marginBottom: 16 }}>
                    <Button icon={<PlusOutlined />} onClick={addChart}>新增图表</Button>
                  </Space>
                  {editReport.charts.length === 0 ? (
                    <Empty description="暂无图表配置，点击上方按钮新增" />
                  ) : (
                    <List
                      dataSource={[...editReport.charts].sort((a, b) => (a.layout_order || 0) - (b.layout_order || 0))}
                      renderItem={(chart, idx) => (
                        <List.Item
                          key={chart.id}
                          style={{ display: 'block', padding: '8px 0', borderBottom: '1px solid #f0f0f0' }}
                        >
                          <Row gutter={8} style={{ alignItems: 'center' }}>
                            <Col span={4}><Text strong>图表 #{idx + 1}</Text></Col>
                            <Col span={5}><Select size="small" value={chart.chart_type} onChange={(v) => updateChart(chart.id, { chart_type: v })} options={Object.entries(chartTypeMap).map(([k, v]) => ({ value: k, label: v }))} style={{ width: '100%' }} /></Col>
                            <Col span={8}><Input size="small" value={chart.title || ''} placeholder="图表标题（可选）" onChange={(e) => updateChart(chart.id, { title: e.target.value })} /></Col>
                            <Col span={5}><InputNumber size="small" value={chart.layout_order || 0} onChange={(v) => updateChart(chart.id, { layout_order: Number(v) || 0 })} style={{ width: '100%' }} placeholder="排序" /></Col>
                            <Col span={2} style={{ textAlign: 'right' }}><Button type="text" danger size="small" icon={<DeleteOutlined />} onClick={() => removeChart(chart.id)} /></Col>
                          </Row>
                        </List.Item>
                      )}
                    />
                  )}
                </div>
              ),
            },
          ]}
        />
      </Modal>
    </div>
  )
}

// 图表组件：支持多维度 + 多度量
const PlaceholderChart = ({ chartType, data, dimensionFields, metricFields }: {
  chartType: string
  data: any[]
  dimensionFields: string[]
  metricFields: string[]
}) => {
  if (!data || data.length === 0) return <Empty />

  const dims = (dimensionFields && dimensionFields.length > 0) ? dimensionFields : [Object.keys(data[0])[0]]
  const metrics = (metricFields && metricFields.length > 0) ? metricFields : Object.keys(data[0]).filter(k => k !== dims[0]).slice(0, 1)
  if (metrics.length === 0) return <Empty description="无度量字段" />

  // 按维度组合标签升序排序
  const sortedData = [...data].sort((a, b) => {
    const labelA = dims.map((dim: string) => String(a[dim] ?? '')).join(' - ')
    const labelB = dims.map((dim: string) => String(b[dim] ?? '')).join(' - ')
    return labelA.localeCompare(labelB, 'zh-CN', { numeric: true })
  })

  const labels: string[] = sortedData.map((d: any) =>
    dims.map((dim: string) => String(d[dim] ?? '')).join(' - ')
  )

  const metricValues: number[][] = metrics.map((m: string) =>
    sortedData.map((d: any) => {
      const v = d[m]
      return typeof v === 'number' ? v : parseFloat(v) || 0
    })
  )

  const globalMax = Math.max(...metricValues.flat(), 1)

  const metricColors = ['#1890ff', '#52c41a', '#faad14', '#f5222d', '#722ed1', '#13c2c2', '#eb2f96', '#fa8c16', '#a0d911', '#2f54eb']

  const containerRef = useRef<HTMLDivElement>(null)

  // ========== 饼图：每个度量一个饼 ==========
  if (chartType === 'pie') {
    return (
      <div ref={containerRef} style={{ padding: 20 }}>
        <Row gutter={[24, 24]}>
          {metrics.map((metricName, mi) => {
            const values = metricValues[mi]
            const total = values.reduce((a, b) => a + b, 0) || 1
            const pieColors = ['#1890ff', '#52c41a', '#faad14', '#f5222d', '#722ed1', '#13c2c2', '#eb2f96', '#fa8c16', '#a0d911', '#fa541c']
            let accDeg = 0
            const stops: string[] = []
            labels.forEach((_, i) => {
              const start = accDeg
              accDeg += (values[i] / total) * 360
              const end = accDeg
              stops.push(`${pieColors[i % pieColors.length]} ${start}deg ${end}deg`)
            })
            const gradient = `conic-gradient(${stops.join(', ')})`
            return (
              <Col xs={24} sm={metrics.length > 2 ? 12 : 24} md={Math.max(12, Math.floor(24 / metrics.length))} key={metricName}>
                <Card size="small" title={<Text strong>{metricName}</Text>} style={{ height: '100%' }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' }}>
                    <div style={{
                      width: 140, height: 140, borderRadius: '50%',
                      background: gradient,
                      flexShrink: 0,
                      boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
                    }} />
                    <div style={{ flex: 1, minWidth: 120, maxHeight: 160, overflowY: 'auto' }}>
                      {labels.map((label, i) => {
                        const percent = ((values[i] / total) * 100).toFixed(1)
                        return (
                          <div key={i} style={{ display: 'flex', alignItems: 'center', marginBottom: 6, fontSize: 12 }}>
                            <div style={{
                              width: 12, height: 12, borderRadius: 2,
                              background: pieColors[i % pieColors.length],
                              marginRight: 6, flexShrink: 0,
                            }} />
                            <Text style={{ flex: 1, color: '#333', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{label}</Text>
                            <Text style={{ color: '#666', marginLeft: 6, fontSize: 11 }}>{values[i]} ({percent}%)</Text>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                </Card>
              </Col>
            )
          })}
        </Row>
      </div>
    )
  }

  // ========== 柱状图：多度量分组 ==========
  if (chartType === 'column') {
    const groupWidth = Math.min(100, Math.max(40, 500 / labels.length))
    const barWidth = Math.max(8, (groupWidth - 8) / metrics.length - 2)
    return (
      <div ref={containerRef} style={{ padding: 20, overflowX: 'auto' }}>
        <div style={{ minWidth: Math.max(600, labels.length * (groupWidth + 10)) }}>
          <div style={{ display: 'flex', gap: 16, marginBottom: 16, flexWrap: 'wrap' }}>
            {metrics.map((m, mi) => (
              <div key={m} style={{ display: 'flex', alignItems: 'center', fontSize: 12 }}>
                <div style={{ width: 12, height: 12, background: metricColors[mi % metricColors.length], marginRight: 4, borderRadius: 2 }} />
                <Text>{m}</Text>
              </div>
            ))}
          </div>
          <div style={{ display: 'flex', alignItems: 'flex-end', height: 300, gap: 4, borderBottom: '1px solid #ddd', borderLeft: '1px solid #ddd', padding: '20px 10px 30px 20px', position: 'relative' }}>
            {[0.25, 0.5, 0.75, 1].map((t, i) => (
              <div key={i} style={{ position: 'absolute', left: 20, right: 10, bottom: 30 + t * 250, borderTop: '1px dashed #eee', pointerEvents: 'none' }} />
            ))}
            {labels.map((label, i) => (
              <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: groupWidth, flexShrink: 0 }}>
                <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 250 }}>
                  {metrics.map((m, mi) => (
                    <div key={m} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-end' }}>
                      <div style={{ fontSize: 9, color: '#333', marginBottom: 2 }}>{metricValues[mi][i]}</div>
                      <div style={{
                        width: barWidth,
                        height: `${Math.max(2, (metricValues[mi][i] / globalMax) * 240)}px`,
                        background: metricColors[mi % metricColors.length],
                        borderRadius: '2px 2px 0 0',
                        transition: 'height 0.3s',
                      }} />
                    </div>
                  ))}
                </div>
                <div style={{ fontSize: 11, color: '#666', marginTop: 6, textAlign: 'center', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', width: groupWidth }}>
                  {label.length > 8 ? label.slice(0, 6) + '...' : label}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  // ========== 条形图：多度量分组 ==========
  if (chartType === 'bar') {
    const barHeight = Math.max(14, 28 / metrics.length)
    return (
      <div ref={containerRef} style={{ padding: 20 }}>
        <div style={{ display: 'flex', gap: 16, marginBottom: 16, flexWrap: 'wrap' }}>
          {metrics.map((m, mi) => (
            <div key={m} style={{ display: 'flex', alignItems: 'center', fontSize: 12 }}>
              <div style={{ width: 12, height: 12, background: metricColors[mi % metricColors.length], marginRight: 4, borderRadius: 2 }} />
              <Text>{m}</Text>
            </div>
          ))}
        </div>
        {labels.map((label, i) => (
          <div key={i} style={{ marginBottom: 10 }}>
            <div style={{ display: 'flex', alignItems: 'center', marginBottom: 2 }}>
              <div style={{ width: 120, textAlign: 'right', paddingRight: 8, fontSize: 11, color: '#666', flexShrink: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{label}</div>
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
                {metrics.map((m, mi) => (
                  <div key={m} style={{ display: 'flex', alignItems: 'center', height: barHeight + 4 }}>
                    <div style={{ flex: 1, height: barHeight, background: '#f5f5f5', borderRadius: 2, position: 'relative' }}>
                      <div style={{
                        background: metricColors[mi % metricColors.length],
                        height: '100%', width: `${Math.max(1, (metricValues[mi][i] / globalMax) * 100)}%`,
                        borderRadius: 2, transition: 'width 0.3s',
                      }} />
                    </div>
                    <span style={{ marginLeft: 6, fontSize: 10, color: '#333', minWidth: 40, textAlign: 'right' }}>{metricValues[mi][i]}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>
    )
  }

  // ========== 折线图：多度量 - 每个指标一条线 ==========
  if (chartType === 'line') {
    const width = Math.max(700, labels.length * 80)
    const height = 360
    const padding = { top: 40, right: 30, bottom: 50, left: 60 }
    const chartW = width - padding.left - padding.right
    const chartH = height - padding.top - padding.bottom
    const stepX = chartW / Math.max(labels.length - 1, 1)

    const metricPoints = metrics.map((m, mi) => ({
      name: m,
      color: metricColors[mi % metricColors.length],
      points: metricValues[mi].map((v, i) => ({
        x: padding.left + i * stepX,
        y: padding.top + chartH - (v / globalMax) * chartH,
        value: v,
      })),
    }))

    const yTicks = [0, 0.25, 0.5, 0.75, 1].map(t => Math.round(globalMax * t))

    return (
      <div ref={containerRef} style={{ padding: 20, overflowX: 'auto' }}>
        <div style={{ display: 'flex', gap: 16, marginBottom: 8, flexWrap: 'wrap' }}>
          {metricPoints.map((mp) => (
            <div key={mp.name} style={{ display: 'flex', alignItems: 'center', fontSize: 12 }}>
              <div style={{ width: 16, height: 3, background: mp.color, marginRight: 4 }} />
              <Text>{mp.name}</Text>
            </div>
          ))}
        </div>
        <svg width={width} height={height} style={{ display: 'block' }}>
          {[0, 0.25, 0.5, 0.75, 1].map((t, i) => {
            const y = padding.top + chartH - t * chartH
            return (
              <g key={i}>
                <line x1={padding.left} y1={y} x2={padding.left + chartW} y2={y} stroke="#eee" />
                <text x={padding.left - 8} y={y + 4} fontSize="11" fill="#999" textAnchor="end">{yTicks[i]}</text>
              </g>
            )
          })}
          <line x1={padding.left} y1={padding.top + chartH} x2={padding.left + chartW} y2={padding.top + chartH} stroke="#ddd" />
          <line x1={padding.left} y1={padding.top} x2={padding.left} y2={padding.top + chartH} stroke="#ddd" />
          {metricPoints.map((mp) => {
            const pathD = mp.points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ')
            return (
              <g key={mp.name}>
                <path d={pathD} fill="none" stroke={mp.color} strokeWidth={2.5} />
                {mp.points.map((p, i) => (
                  <circle key={i} cx={p.x} cy={p.y} r={4} fill="#fff" stroke={mp.color} strokeWidth={2} />
                ))}
              </g>
            )
          })}
          {metricPoints[0].points.map((p, i) => (
            <text key={i} x={p.x} y={padding.top + chartH + 20} fontSize="11" fill="#666" textAnchor="middle">
              {String(labels[i]).slice(0, 8)}
            </text>
          ))}
          {metricPoints[0].points.map((p, i) => (
            <text key={i} x={p.x} y={p.y - 8} fontSize="9" fill="#333" textAnchor="middle">{metricPoints[0].points[i].value}</text>
          ))}
        </svg>
      </div>
    )
  }

  // ========== 面积图：多度量 - 每个指标一个面积 ==========
  if (chartType === 'area') {
    const width = Math.max(700, labels.length * 80)
    const height = 360
    const padding = { top: 40, right: 30, bottom: 50, left: 60 }
    const chartW = width - padding.left - padding.right
    const chartH = height - padding.top - padding.bottom
    const stepX = chartW / Math.max(labels.length - 1, 1)

    const metricPoints = metrics.map((m, mi) => ({
      name: m,
      color: metricColors[mi % metricColors.length],
      points: metricValues[mi].map((v, i) => ({
        x: padding.left + i * stepX,
        y: padding.top + chartH - (v / globalMax) * chartH,
        value: v,
      })),
    }))

    const yTicks = [0, 0.25, 0.5, 0.75, 1].map(t => Math.round(globalMax * t))

    return (
      <div ref={containerRef} style={{ padding: 20, overflowX: 'auto' }}>
        <div style={{ display: 'flex', gap: 16, marginBottom: 8, flexWrap: 'wrap' }}>
          {metricPoints.map((mp) => (
            <div key={mp.name} style={{ display: 'flex', alignItems: 'center', fontSize: 12 }}>
              <div style={{ width: 16, height: 12, background: mp.color, opacity: 0.4, marginRight: 4, borderRadius: 2 }} />
              <Text>{mp.name}</Text>
            </div>
          ))}
        </div>
        <svg width={width} height={height} style={{ display: 'block' }}>
          <defs>
            {metricPoints.map((mp, mi) => (
              <linearGradient key={mi} id={`areaGrad-${mi}`} x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor={mp.color} stopOpacity="0.45" />
                <stop offset="100%" stopColor={mp.color} stopOpacity="0.03" />
              </linearGradient>
            ))}
          </defs>
          {[0, 0.25, 0.5, 0.75, 1].map((t, i) => {
            const y = padding.top + chartH - t * chartH
            return (
              <g key={i}>
                <line x1={padding.left} y1={y} x2={padding.left + chartW} y2={y} stroke="#eee" />
                <text x={padding.left - 8} y={y + 4} fontSize="11" fill="#999" textAnchor="end">{yTicks[i]}</text>
              </g>
            )
          })}
          <line x1={padding.left} y1={padding.top + chartH} x2={padding.left + chartW} y2={padding.top + chartH} stroke="#ddd" />
          <line x1={padding.left} y1={padding.top} x2={padding.left} y2={padding.top + chartH} stroke="#ddd" />
          {metricPoints.map((mp, mi) => {
            const linePath = mp.points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ')
            const areaPath = `${linePath} L ${padding.left + chartW} ${padding.top + chartH} L ${padding.left} ${padding.top + chartH} Z`
            return (
              <g key={mp.name}>
                <path d={areaPath} fill={`url(#areaGrad-${mi})`} />
                <path d={linePath} fill="none" stroke={mp.color} strokeWidth={2.5} />
                {mp.points.map((p, i) => (
                  <circle key={i} cx={p.x} cy={p.y} r={3.5} fill="#fff" stroke={mp.color} strokeWidth={2} />
                ))}
              </g>
            )
          })}
          {metricPoints[0].points.map((p, i) => (
            <text key={i} x={p.x} y={padding.top + chartH + 20} fontSize="11" fill="#666" textAnchor="middle">
              {String(labels[i]).slice(0, 8)}
            </text>
          ))}
        </svg>
      </div>
    )
  }

  return (
    <div ref={containerRef} style={{ padding: 20 }}>
      <Text type="secondary">暂不支持的图表类型</Text>
    </div>
  )
}

export default Report
