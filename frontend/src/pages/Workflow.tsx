import { useState, useEffect } from 'react'
import {
  Card, Button, Space, Modal, Form, Input, Select, message, Tag,
  Spin, Tree, Timeline, Badge, DatePicker, Tooltip, Typography
} from 'antd'
import {
  PlusOutlined, DeleteOutlined, PlayCircleOutlined, SaveOutlined,
  HistoryOutlined, DatabaseOutlined, FileTextOutlined
} from '@ant-design/icons'
import type { DataNode } from 'antd/es/tree'
import api from '../services/api'

const { Title, Text } = Typography
const { TextArea } = Input

interface Folder {
  id: number
  name: string
  parent_id: number | null
  sort_order: number
  created_at: string
  updated_at: string
}

interface Script {
  id: number
  name: string
  folder_id: number
  data_source: string
  sql_content: string | null
  schedule_cron: string | null
  schedule_label: string | null
  status: 'idle' | 'running' | 'success' | 'failed'
  last_run_at: string | null
  created_at: string
  updated_at: string
}

interface LogEntry {
  id: number
  script_id: number
  data_source: string | null
  bizdate: string | null
  status: string
  start_time: string
  end_time: string | null
  duration_ms: number | null
  error_message: string | null
  created_at: string
}

const getStatusColor = (status?: string) => {
  switch (status) {
    case 'success': return 'success'
    case 'failed': return 'error'
    case 'running': return 'processing'
    default: return 'default'
  }
}

const getStatusText = (status?: string) => {
  switch (status) {
    case 'success': return '成功'
    case 'failed': return '失败'
    case 'running': return '运行中'
    default: return '就绪'
  }
}

// 生成 Tree 结构
const generateTreeData = (folders: Folder[], scripts: Script[]): DataNode[] => {
  return folders.map((folder) => ({
    key: `folder-${folder.id}`,
    title: folder.name,
    icon: <DatabaseOutlined style={{ color: '#faad14' }} />,
    children: scripts
      .filter((s) => s.folder_id === folder.id)
      .map((script) => ({
        key: `script-${script.id}`,
        title: (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span>{script.name}</span>
            <Tag color={getStatusColor(script.status)} style={{ marginLeft: 0 }}>
              {getStatusText(script.status)}
            </Tag>
          </div>
        ),
        icon: <FileTextOutlined style={{ color: '#1890ff' }} />,
        isLeaf: true,
      })),
  }))
}

const DEFAULT_DATA_SOURCE = 'pipeline'

const Workflow = () => {
  const [selectedKey, setSelectedKey] = useState<string>('')
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [modalType, setModalType] = useState<'folder' | 'script'>('folder')
  const [form] = Form.useForm()
  const [folders, setFolders] = useState<Folder[]>([])
  const [scripts, setScripts] = useState<Script[]>([])
  const [loading, setLoading] = useState(false)
  const [expandedKeys, setExpandedKeys] = useState<string[]>([])
  const [scriptLogs, setScriptLogs] = useState<LogEntry[]>([])

  // SQL 编辑
  const [editingSql, setEditingSql] = useState<string>('')
  const [sqlDirty, setSqlDirty] = useState(false)

  // 运行参数
  const [runLoading, setRunLoading] = useState(false)
  const [selectedDataSource, setSelectedDataSource] = useState<string>(DEFAULT_DATA_SOURCE)

  const loadData = async () => {
    setLoading(true)
    try {
      const [foldersRes, scriptsRes] = await Promise.all([
        api.get('/workflow/folders'),
        api.get('/workflow/scripts'),
      ])
      const folders = Array.isArray(foldersRes.data) ? foldersRes.data : []
      const scripts = Array.isArray(scriptsRes.data) ? scriptsRes.data : []
      // 确保 sql_content / data_source 字段不为 null/undefined，避免编辑区展示异常
      const normalizedScripts: Script[] = scripts.map((s: any) => ({
        id: s?.id ?? 0,
        name: s?.name ?? '',
        folder_id: s?.folder_id ?? 0,
        data_source: s?.data_source ?? DEFAULT_DATA_SOURCE,
        sql_content: typeof s?.sql_content === 'string' ? s.sql_content : '',
        schedule_cron: s?.schedule_cron ?? null,
        schedule_label: s?.schedule_label ?? null,
        status: s?.status ?? 'idle',
        last_run_at: s?.last_run_at ?? null,
        created_at: s?.created_at ?? '',
        updated_at: s?.updated_at ?? '',
      }))
      setFolders(folders)
      setScripts(normalizedScripts)
    } catch (err: any) {
      message.error(err.response?.data?.detail || '加载数据失败')
      setFolders([])
      setScripts([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  // 选中脚本后加载日志和SQL
  const selectedScript = scripts.find((s) => `script-${s.id}` === selectedKey)
  useEffect(() => {
    if (selectedScript) {
      setEditingSql(selectedScript.sql_content || '')
      setSqlDirty(false)
      setSelectedDataSource(selectedScript.data_source || DEFAULT_DATA_SOURCE)
      loadLogs(selectedScript.id)
    }
  }, [selectedScript?.id])

  const loadLogs = async (scriptId: number) => {
    try {
      const res = await api.get(`/workflow/logs?script_id=${scriptId}&limit=10`)
      setScriptLogs(res.data)
    } catch {
      // ignore
    }
  }

  // SQL 编辑变更 -> dirty
  const handleSqlChange = (value: string) => {
    setEditingSql(value)
    setSqlDirty(value !== (selectedScript?.sql_content || ''))
  }

  const handleSaveSql = async () => {
    if (!selectedScript) return
    try {
      await api.put(`/workflow/scripts/${selectedScript.id}`, {
        sql_content: editingSql,
        data_source: selectedDataSource,
      })
      message.success('保存成功')
      setSqlDirty(false)
      loadData()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '保存失败')
    }
  }

  const handleRunScript = async (bizdate?: string) => {
    if (!selectedScript) return
    setRunLoading(true)
    try {
      const res = await api.post(`/workflow/scripts/${selectedScript.id}/run`, {
        bizdate,
      })
      const result = res.data
      if (result.status === 'success') {
        message.success(
          `执行成功: ${result.executed_statements || 0} 语句, 影响 ${result.affected_rows} 行, 耗时 ${result.duration_ms}ms`
        )
      } else {
        message.error(`执行失败: ${result.error || '未知错误'}`)
      }
      loadData()
      loadLogs(selectedScript.id)
    } catch (err: any) {
      message.error(err.response?.data?.detail || '运行失败')
    } finally {
      setRunLoading(false)
    }
  }

  const handleAdd = (type: 'folder' | 'script') => {
    setModalType(type)
    setIsModalOpen(true)
    form.resetFields()
  }

  const handleModalOk = async () => {
    try {
      const values = await form.validateFields()

      if (modalType === 'folder') {
        await api.post('/workflow/folders', {
          name: values.name,
          sort_order: values.sort_order || 0,
        })
        message.success('目录创建成功')
      } else {
        await api.post('/workflow/scripts', {
          name: values.name,
          folder_id: values.folder_id,
          schedule_cron: values.schedule_cron,
          schedule_label: values.schedule_label,
          data_source: values.data_source || DEFAULT_DATA_SOURCE,
          sql_content: '',
        })
        message.success('脚本创建成功')
      }

      setIsModalOpen(false)
      loadData()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '操作失败')
    }
  }

  const handleDeleteScript = async (id: number) => {
    Modal.confirm({
      title: '确认删除',
      content: '删除后无法恢复，确定要删除该脚本吗？',
      onOk: async () => {
        try {
          await api.delete(`/workflow/scripts/${id}`)
          message.success('删除成功')
          if (selectedKey === `script-${id}`) setSelectedKey('')
          loadData()
        } catch (err: any) {
          message.error(err.response?.data?.detail || '删除失败')
        }
      },
    })
  }

  const scheduleOptions = [
    { value: '0 2 * * *', label: '每日 02:00' },
    { value: '0 3 * * *', label: '每日 03:00' },
    { value: '0 6 * * *', label: '每日 06:00' },
    { value: '0 0 * * *', label: '每日 00:00' },
    { value: '0 * * * *', label: '每小时' },
  ]

  const dataSourceOptions = [
    { value: 'pipeline', label: '数仓层 (MySQL Pipeline)' },
    { value: 'mysql', label: '工作流 MySQL' },
    { value: 'clickhouse', label: 'ClickHouse' },
  ]

  const onSelect = (keys: React.Key[]) => {
    const key = keys[0] as string
    if (key?.startsWith('script-')) {
      setSelectedKey(key)
    } else {
      setSelectedKey('')
    }
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
        <Spin size="large" />
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 48px)' }}>
      {/* 左侧目录树 */}
      <div style={{ width: 320, borderRight: '1px solid #f0f0f0', padding: 16, overflow: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <Text strong>工作流目录</Text>
          <Space>
            <Button type="text" size="small" icon={<PlusOutlined />} onClick={() => handleAdd('folder')} />
            <Button type="text" size="small" icon={<FileTextOutlined />} onClick={() => handleAdd('script')} />
          </Space>
        </div>

        {folders.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 20 }}>
            <Text type="secondary">暂无目录，请先创建</Text>
          </div>
        ) : (
          <Tree
            showIcon
            treeData={generateTreeData(folders, scripts)}
            expandedKeys={expandedKeys}
            onExpand={(keys) => setExpandedKeys(keys as string[])}
            selectedKeys={[selectedKey]}
            onSelect={onSelect}
          />
        )}
      </div>

      {/* 右侧内容区 */}
      <div style={{ flex: 1, padding: 16, overflow: 'auto' }}>
        {selectedScript ? (
          <>
            {/* 头部: 名称 + 状态 + 操作 */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
              <div>
                <Title level={4} style={{ margin: 0 }}>{selectedScript.name}</Title>
                <Space style={{ marginTop: 8 }} wrap>
                  <Tag color={getStatusColor(selectedScript.status)}>{getStatusText(selectedScript.status)}</Tag>
                  <Tag color="blue">数据源: {selectedScript.data_source}</Tag>
                  {selectedScript.schedule_label && <Tag>{selectedScript.schedule_label}</Tag>}
                  {selectedScript.last_run_at && (
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      上次运行: {new Date(selectedScript.last_run_at).toLocaleString()}
                    </Text>
                  )}
                </Space>
              </div>

              <Space>
                <Select
                  size="middle"
                  value={selectedDataSource}
                  style={{ width: 200 }}
                  onChange={(v) => {
                    setSelectedDataSource(v)
                    setSqlDirty(true)
                  }}
                  options={dataSourceOptions}
                />
                <Tooltip title={sqlDirty ? 'SQL 有未保存修改' : ''}>
                  <Button icon={<SaveOutlined />} onClick={handleSaveSql} disabled={!sqlDirty}>
                    {sqlDirty ? '保存' : '已保存'}
                  </Button>
                </Tooltip>
                <Button danger icon={<DeleteOutlined />} onClick={() => handleDeleteScript(selectedScript.id)}>
                  删除
                </Button>
              </Space>
            </div>

            {/* SQL 编辑区 + 运行参数 */}
            <Card
              title="SQL 脚本"
              size="small"
              extra={<Text type="secondary">{editingSql.length} 字符</Text>}
              style={{ marginBottom: 16 }}
            >
              <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'flex-start' }}>
                <Space>
                  <Button
                    type="primary"
                    icon={<PlayCircleOutlined />}
                    loading={runLoading}
                    onClick={() => {
                      // T+1：T=今天-1，所以 T+1 = 今天（实际值为昨天）
                      const yesterday = new Date()
                      yesterday.setDate(yesterday.getDate() - 1)
                      handleRunScript(yesterday.toISOString().slice(0, 10))
                    }}
                    disabled={selectedScript.status === 'running'}
                  >
                    运行脚本（T+1）
                  </Button>
                  <Button
                    type="default"
                    icon={<PlayCircleOutlined />}
                    loading={runLoading}
                    onClick={() => {
                      Modal.confirm({
                        title: '指定业务日期运行',
                        content: (
                          <div style={{ marginTop: 12 }}>
                            <DatePicker
                              id="runBizdatePicker"
                              style={{ width: '100%' }}
                              placeholder="选择 YYYY-MM-DD"
                              onChange={(_date, dateStr) => {
                                (window as any).__selectedBizdate = dateStr
                              }}
                            />
                            <Text type="secondary" style={{ display: 'block', marginTop: 8, fontSize: 12 }}>
                              运行时会把 SQL 中的 {'${bizdate}'} 替换为所选日期
                            </Text>
                          </div>
                        ),
                        onOk: () => {
                          const bizdate = (window as any).__selectedBizdate || new Date().toISOString().slice(0, 10)
                          handleRunScript(bizdate)
                        },
                      })
                    }}
                    disabled={selectedScript.status === 'running'}
                  >
                    指定日期运行
                  </Button>
                </Space>
              </div>

              <TextArea
                value={editingSql}
                onChange={(e) => handleSqlChange(e.target.value)}
                rows={14}
                style={{
                  fontFamily: 'Menlo, Monaco, Consolas, Courier New, monospace',
                  fontSize: 13,
                  background: '#fafafa',
                  borderColor: sqlDirty ? '#1890ff' : undefined,
                }}
                placeholder="-- 输入 SQL 脚本内容，支持 ${bizdate} 变量自动替换"
              />
              <div style={{ marginTop: 8, fontSize: 12, color: '#999' }}>
                提示: SQL 中可使用 {'${bizdate}'} 变量，运行时会根据你选择的日期替换为 YYYY-MM-DD
              </div>
            </Card>

            {/* 运行日志 */}
            <Card
              title={
                <Space>
                  <HistoryOutlined />
                  <span>运行日志</span>
                  {scriptLogs.length > 0 && (
                    <Badge count={scriptLogs.length} style={{ backgroundColor: '#52c41a' }} />
                  )}
                </Space>
              }
              size="small"
            >
              {scriptLogs.length === 0 ? (
                <Text type="secondary">暂无运行记录</Text>
              ) : (
                <Timeline
                  items={scriptLogs.map((log) => ({
                    color: log.status === 'success' ? 'green' : log.status === 'failed' ? 'red' : 'blue',
                    children: (
                      <div>
                        <Space>
                          <Tag color={getStatusColor(log.status)}>{getStatusText(log.status)}</Tag>
                          {log.data_source && <Tag color="purple">ds: {log.data_source}</Tag>}
                          {log.bizdate && <Tag color="cyan">bizdate: {log.bizdate}</Tag>}
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            {new Date(log.start_time).toLocaleString()}
                          </Text>
                          {log.duration_ms && (
                            <Text type="secondary" style={{ fontSize: 12 }}>
                              耗时 {log.duration_ms}ms
                            </Text>
                          )}
                        </Space>
                        {log.error_message && (
                          <div style={{ marginTop: 4, color: '#ff4d4f', fontSize: 12, whiteSpace: 'pre-wrap' }}>
                            {log.error_message}
                          </div>
                        )}
                      </div>
                    ),
                  }))}
                />
              )}
            </Card>
          </>
        ) : (
          <div style={{ textAlign: 'center', padding: 60 }}>
            <FileTextOutlined style={{ fontSize: 64, color: '#d9d9d9' }} />
            <div style={{ marginTop: 16, fontSize: 14, color: '#999' }}>
              请从左侧选择脚本查看详情（或新建脚本）
            </div>
          </div>
        )}
      </div>

      {/* 新建弹窗 */}
      <Modal
        title={modalType === 'folder' ? '新建目录' : '新建脚本'}
        open={isModalOpen}
        onOk={handleModalOk}
        onCancel={() => setIsModalOpen(false)}
      >
        <Form form={form} layout="vertical" style={{ marginTop: 8 }}>
          <Form.Item
            label="名称"
            name="name"
            rules={[{ required: true, message: '请输入名称' }]}
          >
            <Input placeholder={modalType === 'folder' ? '例如：DWD层明细' : '例如：dwd_user_event_daily'} />
          </Form.Item>

          {modalType === 'folder' && (
            <Form.Item label="排序序号" name="sort_order" initialValue={0}>
              <Input type="number" placeholder="数字越小越靠前" />
            </Form.Item>
          )}

          {modalType === 'script' && (
            <>
              <Form.Item
                label="所属目录"
                name="folder_id"
                rules={[{ required: true, message: '请选择所属目录' }]}
              >
                <Select placeholder="选择目录">
                  {folders.map((folder) => (
                    <Select.Option key={folder.id} value={folder.id}>
                      {folder.name}
                    </Select.Option>
                  ))}
                </Select>
              </Form.Item>
              <Form.Item
                label="数据源"
                name="data_source"
                initialValue={DEFAULT_DATA_SOURCE}
              >
                <Select options={dataSourceOptions} />
              </Form.Item>
              <Form.Item label="调度周期" name="schedule_label">
                <Select placeholder="选择调度周期（可选）" options={scheduleOptions} allowClear />
              </Form.Item>
            </>
          )}
        </Form>
      </Modal>
    </div>
  )
}

export default Workflow
