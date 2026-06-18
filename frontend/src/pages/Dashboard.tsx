import { useState, useRef, useEffect, useMemo } from 'react'
import {
  Card, Input, Button, Typography, List, Tag, Space, Divider,
  message, Spin, Tooltip, Modal, Steps, Descriptions,
  Empty, Select, InputNumber, Badge
} from 'antd'
import {
  SendOutlined, UserOutlined, RobotOutlined, CopyOutlined,
  ThunderboltOutlined, DatabaseOutlined, FileTextOutlined,
  CheckCircleOutlined, LoadingOutlined, SaveOutlined,
  EyeOutlined, EyeInvisibleOutlined, PlusOutlined, DeleteOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import api from '../services/api'

const { Title, Text, Paragraph } = Typography
const { TextArea } = Input

// ==================== 类型定义 ====================

interface PipelineResult {
  demand_analysis: string
  tables: Array<{
    layer: string
    table_name: string
    description: string
    ddl_sql: string
    insert_sql: string
    fields: Array<{ name: string; type: string; comment: string }>
    depends_on?: string[]
  }>
  clickhouse_tables: Array<{
    source_ads_table: string
    ch_table_name: string
    engine: string
    order_by: string
    partition_by: string
    ddl_sql: string
    field_mapping: Array<{ source_field: string; target_field: string; type_convert: string }>
  }>
  sync_scripts: Array<{
    name: string
    source_table: string
    target_table: string
    sync_fields: string[]
    filter_condition: string
  }>
  execution_order: string[]
  report_cfg?: {
    report_name: string
    report_desc: string
    category: string
    data_source: string
    ch_table_name: string
    suggested_chart: string
    dimension_fields: string[]
    metric_fields: string[]
  }
}

interface GenerationStep {
  key: string
  label: string
  status: 'wait' | 'process' | 'finish' | 'error'
  description?: string
}

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  pipelineResult?: PipelineResult
  steps?: GenerationStep[]
  persisted?: boolean
  timestamp: Date
}

// ==================== 辅助：从链路中推断报表配置（预览用）====================

interface ReportConfigPreview {
  report_name: string
  report_desc: string
  data_source: string
  ch_table_name: string
  dimension_fields: string[]
  metric_fields: string[]
  suggested_chart: string
}

const inferReportConfig = (result: PipelineResult): ReportConfigPreview | null => {
  if (!result.tables || result.tables.length === 0) return null
  const adsTable = result.tables.find(t => t.layer === 'ads') || result.tables[result.tables.length - 1]
  const chTable = (result.clickhouse_tables && result.clickhouse_tables.length > 0)
    ? result.clickhouse_tables[0]
    : null

  const fields = adsTable.fields || []
  const dimensionFields = fields
    .filter(f => {
      const n = (f.name || '').toLowerCase()
      const c = (f.comment || '').toLowerCase()
      return (
        n !== 'dt' && n !== 'day' &&
        (['id', 'name', 'category', 'region', 'date', 'dt', 'gender', 'department',
          '类别', '区域', '部门', '性别', '地区', '日期'].some(k => n.includes(k) || c.includes(k)))
      )
    })
    .map(f => f.name)
  const metricFields = fields
    .filter(f => {
      const n = (f.name || '').toLowerCase()
      const c = (f.comment || '').toLowerCase()
      return (
        ['count', 'sum', 'amount', 'total', 'cnt', 'gmv', 'avg', 'revenue',
          '数量', '金额', '总计', '销售额', '收入', '平均'].some(k => n.includes(k) || c.includes(k))
      )
    })
    .map(f => f.name)

  // 如果没找到，用简单规则：前 1~2 个文本字段作为维度，后面的数字字段作为指标
  const finalDim = dimensionFields.length > 0
    ? dimensionFields
    : fields.slice(0, Math.min(1, fields.length)).map(f => f.name)
  const finalMetric = metricFields.length > 0
    ? metricFields
    : fields.slice(Math.min(2, fields.length), Math.min(5, fields.length)).map(f => f.name)

  // 图表建议
  const dimCount = finalDim.length
  let suggestedChart = 'table'
  let suggestedChartLabel = '表格'
  if (dimCount === 1 && finalMetric.length >= 1) {
    suggestedChart = 'column'
    suggestedChartLabel = '柱状图'
  } else if (dimCount === 2 && finalMetric.length === 1) {
    suggestedChart = 'table'
    suggestedChartLabel = '表格'
  } else if (finalDim.some(d => /date|day|dt/i.test(d))) {
    suggestedChart = 'line'
    suggestedChartLabel = '折线图'
  }

  return {
    report_name: `报表-${adsTable.table_name.replace('pipeline.', '')}`,
    report_desc: result.demand_analysis || '',
    category: adsTable.description || 'AI生成',
    data_source: 'clickhouse',
    ch_table_name: chTable?.ch_table_name || adsTable.table_name,
    dimension_fields: finalDim.slice(0, 3),
    metric_fields: finalMetric.slice(0, 5),
    suggested_chart: suggestedChart,
    suggested_chart_label: suggestedChartLabel,
  }
}

// ==================== 工具：复制 ====================

const copyToClipboard = (text: string) => {
  navigator.clipboard.writeText(text).then(() => {
    message.success('已复制到剪贴板')
  }).catch(() => {
    message.error('复制失败')
  })
}

const LAYER_COLORS: Record<string, string> = {
  dwd: 'blue',
  dim: 'purple',
  dws: 'cyan',
  ads: 'green',
}

// ==================== 组件 ====================

const Dashboard = () => {
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [messages, setMessages] = useState<Message[]>([])
  const [persistLoading, setPersistLoading] = useState<string | null>(null)
  const [expandedDetails, setExpandedDetails] = useState<Set<string>>(new Set())
  const [previewResult, setPreviewResult] = useState<{ result: PipelineResult; messageId: string } | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()

  // 会话 ID（用于多轮对话）- 从 localStorage 恢复
  const [sessionId, setSessionId] = useState<string | null>(() => {
    return localStorage.getItem('pipeline_session_id')
  })
  
  // 当 sessionId 变化时，同步到 localStorage
  useEffect(() => {
    if (sessionId) {
      localStorage.setItem('pipeline_session_id', sessionId)
    } else {
      localStorage.removeItem('pipeline_session_id')
    }
  }, [sessionId])
  // 模型选择
  const [selectedModel, setSelectedModel] = useState<string>('deepseek-v4-pro')
  // 提交弹框中的向量库配置
  const [persistChunkSize, setPersistChunkSize] = useState<number>(1500)
  const [persistSeparators, setPersistSeparators] = useState<string[]>([';', ',', ' '])

  // ===== 多轮会话结果自动合并（表名相同则覆盖，不同则新增）=====
  const mergedResult = useMemo(() => {
    // 过滤所有包含 pipelineResult 的消息
    const results = messages
      .filter(m => m.pipelineResult)
      .map(m => m.pipelineResult!)

    if (results.length === 0) {
      return null
    }

    // 使用 Map 存储，按表名去重（最新的覆盖旧的）
    const tablesMap = new Map<string, typeof results[0]['tables'][0]>()
    const chTablesMap = new Map<string, typeof results[0]['clickhouse_tables'][0]>()
    const syncScriptsMap = new Map<string, typeof results[0]['sync_scripts'][0]>()
    const demandAnalyses: string[] = []

    // 遍历所有结果，后面的覆盖前面的
    results.forEach(result => {
      // 收集需求分析
      if (result.demand_analysis) {
        demandAnalyses.push(result.demand_analysis)
      }

      // MySQL 表：按表名去重（确保是数组）
      const tables = Array.isArray(result.tables) ? result.tables : []
      tables.forEach(table => {
        tablesMap.set(table.table_name, table)
      })

      // ClickHouse 表：按表名去重（确保是数组）
      const chTables = Array.isArray(result.clickhouse_tables) ? result.clickhouse_tables : []
      chTables.forEach(table => {
        chTablesMap.set(table.ch_table_name, table)
      })

      // 同步脚本：按名称去重（确保是数组）
      const syncScripts = Array.isArray(result.sync_scripts) ? result.sync_scripts : []
      syncScripts.forEach(script => {
        syncScriptsMap.set(script.name, script)
      })
    })

    // 转换为数组，并按层级排序（DIM -> DWD -> DWS -> ADS）
    const layerOrder: Record<string, number> = { dim: 1, dwd: 2, dws: 3, ads: 4 }
    const mergedTables = Array.from(tablesMap.values()).sort((a, b) => {
      const orderA = layerOrder[a.layer] || 99
      const orderB = layerOrder[b.layer] || 99
      if (orderA !== orderB) return orderA - orderB
      // 同层级内按表名排序，保证稳定的显示顺序
      return (a.table_name || '').localeCompare(b.table_name || '')
    })
    const mergedCHTables = Array.from(chTablesMap.values())
    const mergedSyncScripts = Array.from(syncScriptsMap.values())

    // 构建合并后的结果
    const result: PipelineResult = {
      demand_analysis: demandAnalyses.join('；'),
      tables: mergedTables,
      clickhouse_tables: mergedCHTables,
      sync_scripts: mergedSyncScripts,
      execution_order: mergedTables.map(t => t.table_name),
    }

    return result
  }, [messages])

  // 有新消息时滚动到底部
  useEffect(() => {
    if (messages.length > 0) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages])

  // ===== 将分隔符字符串解析为数组 =====
  const parseSeparators = (str: string): string[] => {
    return str
      .split(',')
      .map((s) => s.trim())
      .filter((s) => s.length > 0)
  }

  // ===== 发送请求 =====
  const handleSend = async () => {
    if (!input.trim() || sending) return
    const userMsgId = Date.now().toString()
    const userMessage: Message = {
      id: userMsgId,
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    }
    setMessages(prev => [...prev, userMessage])

    const userInput = input.trim()
    setInput('')
    setSending(true)

    const initSteps: GenerationStep[] = [
      { key: 'rag', label: 'RAG 检索', status: 'process', description: '从知识库检索相关表结构...' },
      { key: 'generate', label: '生成链路', status: 'wait' },
      { key: 'preview', label: '预览确认', status: 'wait' },
    ]
    const assistantMsgId = (Date.now() + 1).toString()
    const assistantMessage: Message = {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      steps: initSteps,
      timestamp: new Date(),
    }
    setMessages(prev => [...prev, assistantMessage])

    try {
      const res = await api.post('/chat/pipeline', {
        user_input: userInput,
        model: selectedModel,
        session_id: sessionId,  // 传递 session_id 用于多轮对话
      })
      // 保存 session_id
      if (res.data.session_id) {
        setSessionId(res.data.session_id)
      }
      setMessages(prev => prev.map(m => {
        if (m.id !== assistantMsgId) return m
        const updatedSteps: GenerationStep[] = [
          { key: 'rag', label: 'RAG 检索', status: 'finish', description: '检索完成' },
          { key: 'generate', label: '生成链路', status: 'finish', description: '已生成完整链路' },
          { key: 'preview', label: '预览确认', status: 'process', description: '请在下方预览并确认' },
        ]
        return { ...m, pipelineResult: res.data as PipelineResult, steps: updatedSteps }
      }))
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || '生成失败，请稍后重试'
      message.error(errorMsg)
      setMessages(prev => prev.map(m => {
        if (m.id !== assistantMsgId) return m
        const updatedSteps: GenerationStep[] = m.steps?.map(s =>
          s.status === 'process' ? { ...s, status: 'error' as const, description: errorMsg } : s
        ) || []
        return { ...m, content: `❌ ${errorMsg}`, steps: updatedSteps }
      }))
    } finally {
      setSending(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const toggleDetail = (key: string) => {
    setExpandedDetails(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  // ===== 渲染步骤 =====
  const renderSteps = (steps: GenerationStep[]) => (
    <Steps
      size="small"
      current={steps.findIndex(s => s.status === 'process')}
      style={{ marginBottom: 12 }}
      items={steps.map(s => ({
        title: s.label,
        status: s.status === 'wait' ? 'wait' : s.status === 'process' ? 'process' : s.status === 'finish' ? 'finish' : 'error',
        description: s.description,
        icon: s.status === 'process' ? <LoadingOutlined /> : s.status === 'finish' ? <CheckCircleOutlined /> : undefined,
      }))}
    />
  )

  // ===== 渲染链路列表（对话气泡中）=====
  const renderSummarySection = (result: PipelineResult) => {
    const total = (result.tables?.length || 0) + (result.clickhouse_tables?.length || 0) + (result.sync_scripts?.length || 0)
    const dimCount = result.tables?.filter(t => t.layer === 'dim').length || 0
    const dwdCount = result.tables?.filter(t => t.layer === 'dwd').length || 0
    const dwsCount = result.tables?.filter(t => t.layer === 'dws').length || 0
    const adsCount = result.tables?.filter(t => t.layer === 'ads').length || 0

    return (
      <Card
        size="small"
        style={{ marginBottom: 12, background: '#f6ffed' }}
        bodyStyle={{ padding: 12 }}
      >
        <Text strong style={{ fontSize: 13 }}>生成概要（共 {total} 个脚本 / 表）：</Text>
        <div style={{ marginTop: 6 }}>
          {dimCount > 0 && <Tag color={LAYER_COLORS.dim}>DIM层 × {dimCount}</Tag>}
          {dwdCount > 0 && <Tag color={LAYER_COLORS.dwd}>DWD层 × {dwdCount}</Tag>}
          {dwsCount > 0 && <Tag color={LAYER_COLORS.dws}>DWS层 × {dwsCount}</Tag>}
          {adsCount > 0 && <Tag color={LAYER_COLORS.ads}>ADS层 × {adsCount}</Tag>}
          {(result.clickhouse_tables?.length || 0) > 0 && (
            <Tag color="magenta">ClickHouse表 × {result.clickhouse_tables.length}</Tag>
          )}
          {(result.sync_scripts?.length || 0) > 0 && (
            <Tag color="orange">同步脚本 × {result.sync_scripts.length}</Tag>
          )}
        </div>
      </Card>
    )
  }

  // ===== 对话消息渲染 =====
  const renderAssistantMessage = (msg: Message) => {
    const result = msg.pipelineResult
    if (!result) {
      if (msg.steps) {
        return (
          <div>
            {renderSteps(msg.steps)}
            {msg.content && <Text type="secondary">{msg.content}</Text>}
          </div>
        )
      }
      return <Text>{msg.content}</Text>
    }

    return (
      <div>
        {result.demand_analysis && (
          <Card size="small" style={{ marginBottom: 12, background: '#e6f7ff' }} bodyStyle={{ padding: 12 }}>
            <Text strong style={{ fontSize: 12 }}>需求理解：</Text>
            <Paragraph style={{ margin: '4px 0 0 0', fontSize: 13 }}>{result.demand_analysis}</Paragraph>
          </Card>
        )}

        {renderSummarySection(result)}

        {/* 入口按钮：预览详细内容 & 确认（显示合并后的结果）*/}
        <Space style={{ marginTop: 4 }} wrap>
          <Button
            type="primary"
            icon={<EyeOutlined />}
            onClick={() => {
              // 使用合并后的结果（自动去重：表名相同则覆盖，不同则新增）
              const displayResult = mergedResult || result
              setPreviewResult({ result: displayResult, messageId: msg.id })
            }}
          >
            预览链路代码 & 报表配置
          </Button>
        </Space>
      </div>
    )
  }

  // ===== 预览模态：展示完整链路 + 报表配置 =====
  const renderPreviewModal = () => {
    if (!previewResult) return null
    const { result, messageId } = previewResult
    const reportCfg = inferReportConfig(result)
    const isPersisted = messages.find(m => m.id === messageId)?.persisted

    return (
      <Modal
        title="链路预览 & 报表配置"
        open={true}
        onCancel={() => setPreviewResult(null)}
        width={920}
        footer={[
          <Button key="cancel" onClick={() => setPreviewResult(null)}>
            关闭
          </Button>,
          <Button
            key="submit"
            type="primary"
            icon={<SaveOutlined />}
            loading={persistLoading === messageId}
            disabled={isPersisted}
            onClick={() => handlePersist(result, messageId, reportCfg)}
          >
            {isPersisted ? '已写入工作流' : '确认并写入工作流'}
          </Button>,
        ]}
      >
        {/* 需求理解 */}
        {result.demand_analysis && (
          <Card size="small" title="需求理解" style={{ marginBottom: 12 }}>
            <Text>{result.demand_analysis}</Text>
          </Card>
        )}

        {/* MySQL 表详情 */}
        {result.tables?.length > 0 && (
          <Card size="small" title={`MySQL 表（${result.tables.length} 个）`} style={{ marginBottom: 12 }}>
            <List
              size="small"
              dataSource={[...result.tables].sort((a, b) => {
                const layerOrder: Record<string, number> = { dim: 1, dwd: 2, dws: 3, ads: 4 }
                const orderA = layerOrder[a.layer] || 99
                const orderB = layerOrder[b.layer] || 99
                if (orderA !== orderB) return orderA - orderB
                return (a.table_name || '').localeCompare(b.table_name || '')
              })}
              style={{ background: '#fafafa', borderRadius: 6 }}
              renderItem={(t) => {
                const key = `p-mysql-${t.table_name}`
                const isExpanded = expandedDetails.has(key)
                const fullScript = (t.ddl_sql || '').trim() +
                  (t.insert_sql ? '\n\n-- 数据加工逻辑\n' + t.insert_sql.trim() : '')
                return (
                  <List.Item
                    style={{ padding: '8px 12px' }}
                    actions={[
                      <Button
                        type="link" size="small"
                        icon={isExpanded ? <EyeInvisibleOutlined /> : <EyeOutlined />}
                        onClick={() => toggleDetail(key)}
                      >
                        {isExpanded ? '收起' : '查看脚本'}
                      </Button>,
                      <Button type="link" size="small" icon={<CopyOutlined />} onClick={() => copyToClipboard(fullScript)}>复制</Button>,
                    ]}
                  >
                    <div style={{ flex: 1 }}>
                      <Space>
                        <Tag color={LAYER_COLORS[t.layer] || 'default'}>{t.layer.toUpperCase()}</Tag>
                        <Text code style={{ fontSize: 12 }}>{t.table_name}</Text>
                        {t.description && <Text type="secondary" style={{ fontSize: 12 }}>— {t.description}</Text>}
                      </Space>
                      {t.depends_on && t.depends_on.length > 0 && (
                        <div style={{ marginTop: 4 }}>
                          <Text type="secondary" style={{ fontSize: 11 }}>上游：</Text>
                          {t.depends_on.map((d, i) => (
                            <Tag key={i} style={{ fontSize: 11, padding: '0 6px' }}>{d}</Tag>
                          ))}
                        </div>
                      )}
                      {isExpanded && (
                        <pre style={{
                          background: '#fff',
                          padding: 8,
                          borderRadius: 4,
                          fontSize: 11,
                          marginTop: 6,
                          fontFamily: 'Monaco, Consolas, monospace',
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                          maxHeight: 360,
                          overflow: 'auto',
                          border: '1px solid #e0e0e0',
                        }}>
                          {fullScript}
                        </pre>
                      )}
                    </div>
                  </List.Item>
                )
              }}
            />
          </Card>
        )}

        {/* ClickHouse 表 */}
        {result.clickhouse_tables?.length > 0 && (
          <Card size="small" title={`ClickHouse 表（${result.clickhouse_tables.length} 个）`} style={{ marginBottom: 12 }}>
            <List
              size="small"
              dataSource={result.clickhouse_tables}
              style={{ background: '#fafafa', borderRadius: 6 }}
              renderItem={(t) => {
                const key = `p-ch-${t.ch_table_name}`
                const isExpanded = expandedDetails.has(key)
                return (
                  <List.Item
                    style={{ padding: '8px 12px' }}
                    actions={[
                      <Button type="link" size="small" icon={isExpanded ? <EyeInvisibleOutlined /> : <EyeOutlined />} onClick={() => toggleDetail(key)}>
                        {isExpanded ? '收起' : '查看 DDL'}
                      </Button>,
                      <Button type="link" size="small" icon={<CopyOutlined />} onClick={() => copyToClipboard(t.ddl_sql)}>复制</Button>,
                    ]}
                  >
                    <div style={{ flex: 1 }}>
                      <Space>
                        <Tag color="purple">CH</Tag>
                        <Text code style={{ fontSize: 12 }}>{t.ch_table_name}</Text>
                      </Space>
                      <div style={{ marginTop: 4 }}>
                        <Text type="secondary" style={{ fontSize: 11 }}>
                          来源：{t.source_ads_table} | 引擎：{t.engine} | 分区：{t.partition_by || '-'} | 排序：{t.order_by}
                        </Text>
                      </div>
                      {isExpanded && (
                        <pre style={{
                          background: '#fff',
                          padding: 8,
                          borderRadius: 4,
                          fontSize: 11,
                          marginTop: 6,
                          fontFamily: 'Monaco, Consolas, monospace',
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                          maxHeight: 360,
                          overflow: 'auto',
                          border: '1px solid #e0e0e0',
                        }}>
                          {t.ddl_sql}
                        </pre>
                      )}
                    </div>
                  </List.Item>
                )
              }}
            />
          </Card>
        )}

        {/* 同步脚本 */}
        {result.sync_scripts?.length > 0 && (
          <Card size="small" title={`同步脚本（${result.sync_scripts.length} 个）`} style={{ marginBottom: 12 }}>
            <List
              size="small"
              dataSource={result.sync_scripts}
              style={{ background: '#fafafa', borderRadius: 6 }}
              renderItem={(s) => {
                const key = `p-sync-${s.name}`
                const isExpanded = expandedDetails.has(key)
                return (
                  <List.Item
                    style={{ padding: '8px 12px' }}
                    actions={[
                      <Button type="link" size="small" icon={isExpanded ? <EyeInvisibleOutlined /> : <EyeOutlined />} onClick={() => toggleDetail(key)}>
                        {isExpanded ? '收起' : '查看详情'}
                      </Button>,
                    ]}
                  >
                    <div style={{ flex: 1 }}>
                      <Space>
                        <Tag color="orange"><ThunderboltOutlined /></Tag>
                        <Text style={{ fontSize: 12 }}>{s.name}</Text>
                      </Space>
                      <div style={{ marginTop: 4 }}>
                        <Text type="secondary" style={{ fontSize: 11 }}>
                          {s.source_table} → {s.target_table}
                        </Text>
                      </div>
                      {isExpanded && (
                        <div style={{
                          background: '#fff7e6',
                          padding: 8,
                          borderRadius: 4,
                          marginTop: 6,
                          border: '1px solid #ffd591',
                        }}>
                          <div style={{ marginBottom: 4 }}>
                            <Text strong style={{ fontSize: 11 }}>同步字段：</Text>
                            <Text code style={{ fontSize: 11 }}>{s.sync_fields?.join(', ')}</Text>
                          </div>
                          <div>
                            <Text strong style={{ fontSize: 11 }}>筛选条件：</Text>
                            <Text code style={{ fontSize: 11 }}>{s.filter_condition}</Text>
                          </div>
                        </div>
                      )}
                    </div>
                  </List.Item>
                )
              }}
            />
          </Card>
        )}

        {/* 执行顺序 */}
        {result.execution_order?.length > 0 && (
          <Card size="small" title="执行顺序" style={{ marginBottom: 12 }}>
            <Space wrap>
              {result.execution_order.map((step, i) => (
                <Tag key={i} color="green">{i + 1}. {step}</Tag>
              ))}
            </Space>
          </Card>
        )}

        {/* 向量数据库配置（存入知识库） */}
        <Card size="small" title="向量数据库配置" style={{ marginBottom: 12 }}>
          <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 12 }}>
            确认提交后，脚本内容将自动存入知识库向量数据库，供后续 RAG 检索使用
          </Text>
          <Space size="large" wrap>
            <div>
              <Text style={{ fontSize: 12 }}>向量块大小：</Text>
              <InputNumber
                size="small"
                value={persistChunkSize}
                min={100}
                max={10000}
                step={100}
                onChange={(v) => setPersistChunkSize(Number(v) || 1500)}
                style={{ marginLeft: 8, width: 100 }}
              />
            </div>
            <div style={{ minWidth: 300 }}>
              <Text style={{ fontSize: 12 }}>自定义分隔符：</Text>
              <Select
                mode="tags"
                size="small"
                value={persistSeparators}
                onChange={(v) => setPersistSeparators(v as string[])}
                placeholder="输入分隔符后回车（可多个）"
                style={{ marginLeft: 8, width: 220 }}
                tokenSeparators={[',']}
              />
            </div>
          </Space>
        </Card>

        {/* 报表配置预览 */}
        {reportCfg && (
          <Card size="small" title="报表配置预览（建议）" style={{ marginBottom: 12 }}>
            <Descriptions column={2} size="small" bordered>
              <Descriptions.Item label="报表名称" span={2}>{reportCfg.report_name}</Descriptions.Item>
              <Descriptions.Item label="报表描述" span={2}>{reportCfg.report_desc}</Descriptions.Item>
              <Descriptions.Item label="数据源">{reportCfg.data_source}</Descriptions.Item>
              <Descriptions.Item label="目标表">{reportCfg.ch_table_name}</Descriptions.Item>
              <Descriptions.Item label="建议图表类型">{reportCfg.suggested_chart_label}</Descriptions.Item>
              <Descriptions.Item label="维度字段">
                {reportCfg.dimension_fields.length > 0
                  ? reportCfg.dimension_fields.map((d, i) => <Tag key={i}>{d}</Tag>)
                  : <Text type="secondary">未识别</Text>}
              </Descriptions.Item>
              <Descriptions.Item label="指标字段" span={2}>
                {reportCfg.metric_fields.length > 0
                  ? reportCfg.metric_fields.map((m, i) => <Tag key={i} color="cyan">{m}</Tag>)
                  : <Text type="secondary">未识别</Text>}
              </Descriptions.Item>
            </Descriptions>
          </Card>
        )}

        {/* 无报表配置提示 */}
        {!reportCfg && (
          <Empty description="无法推断报表配置" style={{ marginBottom: 12 }} />
        )}
      </Modal>
    )
  }

  // ===== 将脚本内容合并为文本 =====
  const mergeScriptsToText = (result: PipelineResult): string => {
    const parts: string[] = []

    // 需求分析
    if (result.demand_analysis) {
      parts.push(`======= 需求分析 =======\n${result.demand_analysis}\n`)
    }

    // MySQL 表脚本
    if (result.tables?.length > 0) {
      parts.push(`\n======= MySQL 表脚本 (${result.tables.length} 个) =======`)
      result.tables.forEach((table) => {
        parts.push(`\n--- ${table.layer.toUpperCase()}层: ${table.table_name} ---`)
        parts.push(`描述: ${table.description || '无'}`)
        if (table.depends_on?.length > 0) {
          parts.push(`依赖: ${table.depends_on.join(', ')}`)
        }
        if (table.ddl_sql) {
          parts.push(`DDL:\n${table.ddl_sql}`)
        }
        if (table.insert_sql) {
          parts.push(`INSERT:\n${table.insert_sql}`)
        }
      })
    }

    // ClickHouse 表脚本
    if (result.clickhouse_tables?.length > 0) {
      parts.push(`\n======= ClickHouse 表脚本 (${result.clickhouse_tables.length} 个) =======`)
      result.clickhouse_tables.forEach((table) => {
        parts.push(`\n--- ${table.ch_table_name} ---`)
        parts.push(`来源: ${table.source_ads_table}`)
        parts.push(`引擎: ${table.engine}`)
        parts.push(`排序: ${table.order_by}`)
        if (table.partition_by) {
          parts.push(`分区: ${table.partition_by}`)
        }
        if (table.ddl_sql) {
          parts.push(`DDL:\n${table.ddl_sql}`)
        }
      })
    }

    // 同步脚本
    if (result.sync_scripts?.length > 0) {
      parts.push(`\n======= 同步脚本 (${result.sync_scripts.length} 个) =======`)
      result.sync_scripts.forEach((script) => {
        parts.push(`\n--- ${script.name} ---`)
        parts.push(`源表: ${script.source_table}`)
        parts.push(`目标表: ${script.target_table}`)
        parts.push(`同步字段: ${script.sync_fields?.join(', ') || '无'}`)
        parts.push(`筛选条件: ${script.filter_condition || '无'}`)
      })
    }

    // 执行顺序
    if (result.execution_order?.length > 0) {
      parts.push(`\n======= 执行顺序 =======`)
      result.execution_order.forEach((step, index) => {
        parts.push(`${index + 1}. ${step}`)
      })
    }

    return parts.join('\n')
  }

  // ===== 写入工作流 =====
  const handlePersist = async (result: PipelineResult, messageId: string, reportCfg: ReturnType<typeof inferReportConfig> | null) => {
    setPersistLoading(messageId)
    try {
      // 1. 写入工作流（包含报表配置和同步脚本执行）
      await api.post('/chat/persist', {
        demand_analysis: result.demand_analysis,
        tables: result.tables,
        clickhouse_tables: result.clickhouse_tables,
        sync_scripts: result.sync_scripts,
        execution_order: result.execution_order,
        report_cfg: reportCfg || null,
      })

      // 2. 将脚本内容合并并存入知识库向量数据库
      const mergedText = mergeScriptsToText(result)
      const sourceName = `数仓链路_${result.demand_analysis?.slice(0, 30) || '未命名'}_${Date.now()}`
      try {
        await api.post('/knowledge/import/text', {
          text: mergedText,
          source_name: sourceName,
          chunk_size: persistChunkSize,
          chunk_overlap: Math.floor(persistChunkSize / 10),
          custom_separators: persistSeparators.length > 0 ? persistSeparators : undefined,
        })
        console.log('脚本内容已成功存入知识库向量数据库')
      } catch (dbErr: any) {
        console.warn('存入知识库失败:', dbErr)
        // 不阻断主流程
      }

      message.success('已成功写入工作流！')
      setMessages(prev => prev.map(m =>
        m.id === messageId
          ? { ...m, persisted: true }
          : m
      ))
      Modal.confirm({
        title: '写入成功',
        content: `已创建 ${(result.tables?.length || 0) + (result.clickhouse_tables?.length || 0) + (result.sync_scripts?.length || 0)} 个脚本，并同步存入知识库。是否跳转查看？`,
        okText: '跳转工作流',
        cancelText: '留在当前页',
        onOk: () => navigate('/workflow'),
        onCancel: () => setPreviewResult(null),
      })
    } catch (err: any) {
      message.error(err.response?.data?.detail || '写入工作流失败')
    } finally {
      setPersistLoading(null)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: 'calc(100vh - 48px)', padding: '0 4px 8px' }}>
      {/* 消息列表 */}
      <div style={{ marginBottom: 16 }}>
        {messages.length === 0 && !sending && (
          <div style={{ textAlign: 'center', padding: '20px 16px 12px' }}>
            {/* 欢迎卡片 */}
            <div style={{
              maxWidth: 500,
              margin: '0 auto',
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              borderRadius: 14,
              padding: 2,
              boxShadow: '0 5px 20px rgba(102, 126, 234, 0.22)',
            }}>
              <Card
                size="small"
                style={{
                  borderRadius: 12,
                  background: 'linear-gradient(180deg, #ffffff 0%, #f8fafc 100%)',
                  border: 'none',
                }}
                bodyStyle={{ padding: 17 }}
              >
                {/* 头像区域 */}
                <div style={{
                  width: 48,
                  height: 48,
                  borderRadius: '50%',
                  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  margin: '0 auto 10px',
                  boxShadow: '0 4px 10px rgba(102, 126, 234, 0.32)',
                }}>
                  <RobotOutlined style={{ fontSize: 22, color: '#fff' }} />
                </div>

                <Title level={5} style={{ textAlign: 'center', marginBottom: 5, color: '#333', fontSize: 18 }}>
                  数仓开发助手
                </Title>
                <Paragraph type="secondary" style={{ marginBottom: 12, fontSize: 12, textAlign: 'center' }}>
                  描述需求，自动生成数仓链路（ODS → DIM → DWD → DWS → ADS → ClickHouse）
                </Paragraph>

                {/* 功能列表 */}
                <div style={{
                  background: 'linear-gradient(180deg, #f6f7ff 0%, #eeeef5 100%)',
                  borderRadius: 9,
                  padding: '10px 14px',
                  marginBottom: 12,
                  textAlign: 'left',
                }}>
                  <ul style={{ margin: 0, paddingLeft: 16 }}>
                    {[
                      'DIM 维表（ODS 抽取，DISTINCT 去重）',
                      'DWD / DWS / ADS 层建表 SQL 与 INSERT',
                      'ClickHouse 建表 DDL 与同步脚本',
                      '报表配置（维度/指标/图表建议）',
                    ].map((text, index) => (
                      <li key={index} style={{ fontSize: 12, color: '#555', marginBottom: 3, lineHeight: 1.6 }}>
                        {text}
                      </li>
                    ))}
                  </ul>
                </div>

                {/* 示例提示 */}
                <div style={{
                  background: 'linear-gradient(135deg, #e6f7ff 0%, #f0f9ff 100%)',
                  borderRadius: 7,
                  padding: '7px 12px',
                  borderLeft: '2px solid #1890ff',
                }}>
                  <Text type="secondary" style={{ fontSize: 11 }}>💡 示例：</Text>
                  <div style={{ marginTop: 2, fontStyle: 'italic', color: '#1890ff', fontSize: 12 }}>
                    "统计每个商品类目的 GMV 和订单数，按日分区"
                  </div>
                </div>
              </Card>
            </div>
          </div>
        )}

        {messages.length > 0 && (
          <List
            dataSource={messages}
            renderItem={(msg) => (
              <List.Item
                style={{
                  justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                  border: 'none',
                  padding: '8px 0',
                }}
              >
                <div style={{
                  maxWidth: '80%',
                  width: '100%',
                  display: 'flex',
                  flexDirection: msg.role === 'user' ? 'row-reverse' : 'row',
                  alignItems: 'flex-start',
                  gap: 12,
                }}>
                  {/* 头像 */}
                  <div style={{
                    width: 40,
                    height: 40,
                    borderRadius: '50%',
                    background: msg.role === 'user'
                      ? 'linear-gradient(135deg, #52c41a 0%, #389e0d 100%)'
                      : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    boxShadow: msg.role === 'user'
                      ? '0 4px 12px rgba(82, 196, 26, 0.3)'
                      : '0 4px 12px rgba(102, 126, 234, 0.3)',
                    flexShrink: 0,
                  }}>
                    {msg.role === 'user'
                      ? <UserOutlined style={{ fontSize: 18, color: '#fff' }} />
                      : <RobotOutlined style={{ fontSize: 18, color: '#fff' }} />
                    }
                  </div>

                  {/* 消息气泡 */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    {/* 用户名标签 */}
                    <div style={{
                      marginBottom: 4,
                      fontSize: 12,
                      color: msg.role === 'user' ? '#52c41a' : '#667eea',
                      textAlign: msg.role === 'user' ? 'right' : 'left',
                    }}>
                      {msg.role === 'user' ? '您' : 'AI 助手'}
                    </div>

                    {/* 消息卡片 */}
                    <Card
                      size="small"
                      style={{
                        background: msg.role === 'user'
                          ? 'linear-gradient(135deg, #e6f7ff 0%, #bae0ff 100%)'
                          : '#fff',
                        border: msg.role === 'user'
                          ? '1px solid #91d5ff'
                          : '1px solid #e8e8e8',
                        borderRadius: msg.role === 'user'
                          ? '16px 16px 4px 16px'
                          : '16px 16px 16px 4px',
                        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.06)',
                      }}
                      bodyStyle={{ padding: msg.role === 'user' ? '12px 16px' : '12px 16px' }}
                    >
                      <div>
                        {msg.role === 'user'
                          ? <Text style={{ color: '#333', lineHeight: 1.6 }}>{msg.content}</Text>
                          : renderAssistantMessage(msg)
                        }
                      </div>
                    </Card>

                    {/* 时间戳和状态 */}
                    <div style={{
                      marginTop: 6,
                      fontSize: 11,
                      color: '#999',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                    }}>
                      <span>{msg.timestamp.toLocaleTimeString()}</span>
                      {msg.persisted && (
                        <Tag color="success" icon={<CheckCircleOutlined />} style={{ margin: 0 }}>
                          已写入工作流
                        </Tag>
                      )}
                    </div>
                  </div>
                </div>
              </List.Item>
            )}
          />
        )}

        {sending && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 0' }}>
            <Spin size="small" />
            <Text type="secondary">AI 正在生成数仓链路...</Text>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* 输入区 */}
      <Card size="small" bodyStyle={{ padding: '10px 14px' }}>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 8 }}>
          <Button
            size="small"
            icon={<PlusOutlined />}
            onClick={() => {
              Modal.confirm({
                title: '新建对话',
                content: '确定要清空当前对话，开始新的会话吗？',
                okText: '确定',
                cancelText: '取消',
                onOk: () => {
                  setMessages([])
                  setSessionId(null)
                  message.success('已开启新对话')
                },
              })
            }}
          >
            新建对话
          </Button>
          {sessionId && (
            <Tag color="blue" style={{ fontSize: 11 }}>
              会话: {sessionId.slice(-8)}
            </Tag>
          )}
          <Text type="secondary" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>模型：</Text>
          <Select
            size="small"
            value={selectedModel}
            onChange={(v) => setSelectedModel(v)}
            style={{ width: 160 }}
            options={[
              { value: 'deepseek-v4-pro', label: 'deepseek-v4-pro（高质量）' },
              { value: 'deepseek-v4-flash', label: 'deepseek-v4-flash（快速）' },
            ]}
            disabled={sending}
          />
          <Text type="secondary" style={{ fontSize: 12 }}>
            输入需求，AI 自动生成数仓链路
          </Text>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <TextArea
            rows={2}
            placeholder="请输入您的数据需求描述，例如：生成一张按类目、日期分区的 GMV 与订单数统计表..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={sending}
            style={{ flex: 1 }}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handleSend}
            loading={sending}
            disabled={!input.trim()}
            style={{ height: 'auto', alignSelf: 'flex-end', minWidth: 72 }}
          >
            发送
          </Button>
        </div>
      </Card>

      {/* 预览模态 */}
      {renderPreviewModal()}
    </div>
  )
}

export default Dashboard
