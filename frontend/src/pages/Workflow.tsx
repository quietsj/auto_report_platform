import { useState, useEffect } from 'react'
import { Card, Button, Space, Modal, Form, Input, Select, message, Tag, Dropdown, Typography, Spin, Tree } from 'antd'
import { PlusOutlined, FolderOutlined, FileOutlined, DeleteOutlined, PlayCircleOutlined } from '@ant-design/icons'
import type { DataNode } from 'antd/es/tree'
import api from '../services/api'

const { Title, Text } = Typography

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
  sql_content: string | null
  schedule_cron: string | null
  schedule_label: string | null
  status: 'idle' | 'running' | 'success' | 'failed'
  last_run_at: string | null
  created_at: string
  updated_at: string
}

// 转换为树形数据
const generateTreeData = (folders: Folder[], scripts: Script[]): DataNode[] => {
  return folders.map((folder) => ({
    key: `folder-${folder.id}`,
    title: folder.name,
    icon: <FolderOutlined style={{ color: '#faad14' }} />,
    children: scripts
      .filter((s) => s.folder_id === folder.id)
      .map((script) => ({
        key: `script-${script.id}`,
        title: (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span>{script.name}</span>
            <Tag color={getStatusColor(script.status)} size="small" style={{ marginLeft: 8 }}>
              {getStatusText(script.status)}
            </Tag>
          </div>
        ),
        icon: <FileOutlined style={{ color: '#1890ff' }} />,
        isLeaf: true,
      })),
  }))
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

const Workflow = () => {
  const [selectedKey, setSelectedKey] = useState<string>('')
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [modalType, setModalType] = useState<'folder' | 'script'>('folder')
  const [form] = Form.useForm()
  const [folders, setFolders] = useState<Folder[]>([])
  const [scripts, setScripts] = useState<Script[]>([])
  const [loading, setLoading] = useState(false)
  const [expandedKeys, setExpandedKeys] = useState<string[]>([])

  // 加载数据
  const loadData = async () => {
    setLoading(true)
    try {
      const [foldersRes, scriptsRes] = await Promise.all([
        api.get('/workflow/folders'),
        api.get('/workflow/scripts'),
      ])
      setFolders(foldersRes.data)
      setScripts(scriptsRes.data)
      // 默认关闭所有目录
      setExpandedKeys([])
    } catch (error: any) {
      message.error(error.response?.data?.detail || '加载数据失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const selectedScript = scripts.find((s) => `script-${s.id}` === selectedKey)

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
          sql_content: '',
        })
        message.success('脚本创建成功')
      }
      
      setIsModalOpen(false)
      loadData()
    } catch (error: any) {
      message.error(error.response?.data?.detail || '操作失败')
    }
  }

  const handleDeleteFolder = async (id: number) => {
    Modal.confirm({
      title: '确认删除',
      content: '删除后无法恢复，确定要删除吗？',
      onOk: async () => {
        try {
          await api.delete(`/workflow/folders/${id}`)
          message.success('删除成功')
          loadData()
        } catch (error: any) {
          message.error(error.response?.data?.detail || '删除失败')
        }
      },
    })
  }

  const handleDeleteScript = async (id: number) => {
    Modal.confirm({
      title: '确认删除',
      content: '删除后无法恢复，确定要删除吗？',
      onOk: async () => {
        try {
          await api.delete(`/workflow/scripts/${id}`)
          message.success('删除成功')
          if (selectedKey === `script-${id}`) setSelectedKey('')
          loadData()
        } catch (error: any) {
          message.error(error.response?.data?.detail || '删除失败')
        }
      },
    })
  }

  const handleRunScript = async (id: number) => {
    try {
      await api.post(`/workflow/scripts/${id}/run`)
      message.success('脚本已启动')
      loadData()
    } catch (error: any) {
      message.error(error.response?.data?.detail || '运行失败')
    }
  }

  const scheduleOptions = [
    { value: '0 2 * * *', label: '每日 02:00' },
    { value: '0 3 * * *', label: '每日 03:00' },
    { value: '0 6 * * *', label: '每日 06:00' },
    { value: '0 0 * * *', label: '每日 00:00' },
    { value: '0 * * * *', label: '每小时' },
  ]

  const menuItems = [
    { key: 'addFolder', label: '新建目录', icon: <FolderOutlined /> },
    { key: 'addScript', label: '新建脚本', icon: <FileOutlined /> },
  ]

  const handleMenuClick = (e: { key: string }) => {
    if (e.key === 'addFolder') handleAdd('folder')
    if (e.key === 'addScript') handleAdd('script')
  }

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
      <div style={{ width: 300, borderRight: '1px solid #f0f0f0', padding: 16, overflow: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <Text strong>工作流目录</Text>
          <Dropdown menu={{ items: menuItems, onClick: handleMenuClick }} trigger={['click']}>
            <Button type="text" size="small" icon={<PlusOutlined />} />
          </Dropdown>
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
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <div>
                <Title level={4} style={{ margin: 0 }}>{selectedScript.name}</Title>
                <Space style={{ marginTop: 8 }}>
                  <Tag color={getStatusColor(selectedScript.status)}>{getStatusText(selectedScript.status)}</Tag>
                  {selectedScript.schedule_label && <Tag>{selectedScript.schedule_label}</Tag>}
                  {selectedScript.last_run_at && (
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      上次运行: {new Date(selectedScript.last_run_at).toLocaleString()}
                    </Text>
                  )}
                </Space>
              </div>
              <Space>
                <Button 
                  icon={<PlayCircleOutlined />} 
                  type="primary"
                  onClick={() => handleRunScript(selectedScript.id)}
                  disabled={selectedScript.status === 'running'}
                >
                  运行
                </Button>
                <Button danger icon={<DeleteOutlined />} onClick={() => handleDeleteScript(selectedScript.id)}>
                  删除
                </Button>
              </Space>
            </div>
            
            <Card title="SQL 脚本" size="small">
              <pre style={{
                background: '#f5f5f5',
                padding: 16,
                borderRadius: 4,
                minHeight: 200,
                fontFamily: 'Monaco, Consolas, monospace',
                fontSize: 13,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}>
                {selectedScript.sql_content || '-- 无内容'}
              </pre>
            </Card>

            <Card title="运行日志" size="small" style={{ marginTop: 16 }}>
              <Text type="secondary">暂无运行记录</Text>
            </Card>
          </>
        ) : (
          <div style={{ textAlign: 'center', padding: 60 }}>
            <FileOutlined style={{ fontSize: 64, color: '#d9d9d9' }} />
            <Title level={5} type="secondary" style={{ marginTop: 16 }}>请从左侧选择脚本查看详情</Title>
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
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            label="名称"
            name="name"
            rules={[{ required: true, message: '请输入名称' }]}
          >
            <Input placeholder={modalType === 'folder' ? '例如：dwd层' : '例如：ads_daily_summary'} />
          </Form.Item>
          
          {modalType === 'folder' && (
            <Form.Item label="排序顺序" name="sort_order" initialValue={0}>
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
              <Form.Item label="调度周期" name="schedule_label">
                <Select placeholder="选择调度周期" options={scheduleOptions} />
              </Form.Item>
            </>
          )}
        </Form>
      </Modal>
    </div>
  )
}

export default Workflow
