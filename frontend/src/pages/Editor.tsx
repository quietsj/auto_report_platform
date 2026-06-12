import {
  Card, Typography, Button, Form, Input, Space, message, List,
  Spin, Alert, Modal, Upload, Progress, Divider, Tag, Popconfirm,
  InputNumber, Select, Empty
} from 'antd'
import {
  DeleteOutlined, PlusOutlined, UploadOutlined, FileTextOutlined, SearchOutlined, SyncOutlined
} from '@ant-design/icons'
import { useEffect, useState } from 'react'
import api from '../services/api'

const { Title, Text, Paragraph } = Typography
const { TextArea } = Input
const { Dragger } = Upload

// ==================== 类型定义 ====================

interface KnowledgeDocument {
  doc_id: string
  source_name: string
  total_chunks: number
  chunk_ids?: string[]
}

interface KnowledgeChunk {
  id: string
  content_preview: string
  chunk_index: number
  total_chunks: number
}

interface ImportResult {
  doc_id: string
  source_name: string
  total_chunks: number
  added_to_vector_db: number
  chunks: KnowledgeChunk[]
}

interface KnowledgeStats {
  total_documents: number
  total_chunks: number
  avg_chunk_size: number
}

interface SearchResult {
  chunk_id: string
  content: string
  metadata: Record<string, any>
  score: number
}

// ==================== 常量 ====================

const SEPARATOR_OPTIONS = [
  { label: '段落分隔（双换行）', value: '\n\n' },
  { label: '单换行', value: '\n' },
  { label: '句号（。）', value: '。' },
  { label: '感叹号（！）', value: '！' },
  { label: '问号（？）', value: '？' },
  { label: '分号（；）', value: '；' },
  { label: '逗号（，）', value: '，' },
]

// ==================== 组件 ====================

const Editor = () => {
  const [form] = Form.useForm()
  const [textForm] = Form.useForm()
  const [searchForm] = Form.useForm()

  // 文件导入参数（用 state 而非 form，避免 getFieldsValue 取值时机问题）
  const [fileChunkSize, setFileChunkSize] = useState(500)
  const [fileChunkOverlap, setFileChunkOverlap] = useState(50)
  const [fileSeparators, setFileSeparators] = useState<string[]>([])

  // 文档列表
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([])
  const [stats, setStats] = useState<KnowledgeStats | null>(null)
  const [loading, setLoading] = useState(false)

  // 导入状态
  const [importModalVisible, setImportModalVisible] = useState(false)
  const [importType, setImportType] = useState<'text' | 'file'>('text')
  const [importing, setImporting] = useState(false)
  const [importProgress, setImportProgress] = useState(0)
  const [importResult, setImportResult] = useState<ImportResult | null>(null)

  // 搜索状态
  const [searchVisible, setSearchVisible] = useState(false)
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [searching, setSearching] = useState(false)

  // ==================== 数据获取 ====================

  const fetchDocuments = async () => {
    setLoading(true)
    try {
      const res = await api.get('/knowledge/documents')
      if (res.data.success) {
        setDocuments(res.data.data.documents || [])
        setStats(res.data.data.stats || null)
      }
    } catch (err: any) {
      message.error(err.response?.data?.detail || '获取文档列表失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchDocuments()
  }, [])

  // ==================== 文本导入 ====================

  const handleTextImport = async (values: any) => {
    setImporting(true)
    setImportProgress(0)
    setImportResult(null)

    try {
      setImportProgress(30)
      const res = await api.post('/knowledge/import/text', {
        text: values.text,
        source_name: values.source_name,
        chunk_size: values.chunk_size || 500,
        chunk_overlap: values.chunk_overlap || 50,
        custom_separators: values.custom_separators || null,
      })

      setImportProgress(100)
      if (res.data.success) {
        setImportResult(res.data.data)
        message.success(`导入成功！共 ${res.data.data.total_chunks} 个块`)
        fetchDocuments()
      }
    } catch (err: any) {
      message.error(err.response?.data?.detail || '导入失败')
    } finally {
      setImporting(false)
    }
  }

  const handleFileImport = async (
    file: File,
    chunkSize?: number,
    chunkOverlap?: number,
    customSeparators?: string[],
  ) => {
    setImporting(true)
    setImportProgress(0)
    setImportResult(null)

    try {
      setImportProgress(20)
      const formData = new FormData()
      formData.append('file', file)
      formData.append('source_name', file.name.replace(/\.[^.]+$/, ''))
      formData.append('chunk_size', String(chunkSize ?? 500))
      formData.append('chunk_overlap', String(chunkOverlap ?? 50))
      if (customSeparators && customSeparators.length > 0) {
        formData.append('custom_separators', JSON.stringify(customSeparators))
      }

      const res = await api.post('/knowledge/import/file', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })

      setImportProgress(100)
      if (res.data.success) {
        setImportResult(res.data.data)
        message.success(`导入成功！共 ${res.data.total_chunks || res.data.data?.total_chunks} 个块`)
        fetchDocuments()
      }
    } catch (err: any) {
      const detail = err.response?.data?.detail
      let errMsg = '文件导入失败'
      if (typeof detail === 'string') {
        errMsg = detail
      } else if (Array.isArray(detail)) {
        // FastAPI 422 错误格式：{type, loc, msg, input}[]
        errMsg = detail.map((e: any) => e.msg || JSON.stringify(e)).join('; ')
      } else if (detail?.message) {
        errMsg = detail.message
      }
      message.error(errMsg)
    } finally {
      setImporting(false)
    }
  }

  // customRequest 完全接管 Dragger 的上传逻辑，避免 beforeUpload 异步冲突
  const customRequest = (options: any) => {
    const { file, onSuccess, onError } = options
    handleFileImport(file as File)
      .then(() => onSuccess())
      .catch((err) => onError(err))
    return { abort() {} }
  }

  // ==================== 文档管理 ====================

  const handleDeleteDocument = async (doc_id: string) => {
    try {
      await api.delete(`/knowledge/documents/${doc_id}`)
      message.success('文档已删除')
      fetchDocuments()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '删除失败')
    }
  }

  // ==================== 搜索 ====================

  const handleSearch = async (values: any) => {
    setSearching(true)
    try {
      const res = await api.post('/knowledge/search', {
        query: values.query,
        top_k: values.top_k || 5,
      })
      if (res.data.success) {
        setSearchResults(res.data.data || [])
        setSearchVisible(true)
      }
    } catch (err: any) {
      message.error(err.response?.data?.detail || '检索失败')
    } finally {
      setSearching(false)
    }
  }

  // ==================== 渲染：知识库文档列表 ====================

  const renderKnowledgeSection = () => (
    <div>
      {/* 统计卡片 */}
      {stats && (
        <div style={{ display: 'flex', gap: 16, marginBottom: 16 }}>
          <Card size="small" style={{ flex: 1 }}>
            <Text type="secondary">文档数</Text>
            <div style={{ fontSize: 24, fontWeight: 'bold', color: '#1890ff' }}>
              {stats.total_documents}
            </div>
          </Card>
          <Card size="small" style={{ flex: 1 }}>
            <Text type="secondary">总块数</Text>
            <div style={{ fontSize: 24, fontWeight: 'bold', color: '#52c41a' }}>
              {stats.total_chunks}
            </div>
          </Card>
          <Card size="small" style={{ flex: 1 }}>
            <Text type="secondary">平均块大小</Text>
            <div style={{ fontSize: 24, fontWeight: 'bold', color: '#722ed1' }}>
              {Math.round(stats.avg_chunk_size)} 字
            </div>
          </Card>
        </div>
      )}

      {/* 操作按钮 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => {
            setImportType('text')
            setImportResult(null)
            setImportProgress(0)
            setImportModalVisible(true)
          }}>
            导入文本
          </Button>
          <Button icon={<UploadOutlined />} onClick={() => {
            setImportType('file')
            setImportResult(null)
            setImportProgress(0)
            setImportModalVisible(true)
          }}>
            导入文件
          </Button>
          <Button icon={<SearchOutlined />} onClick={() => setSearchVisible(true)}>
            检索知识库
          </Button>
          <Button icon={<SyncOutlined />} onClick={fetchDocuments}>
            刷新
          </Button>
        </Space>
      </Card>

      {/* 文档列表 */}
      <Card title="已导入文档" size="small">
        {loading ? (
          <div style={{ textAlign: 'center', padding: 40 }}>
            <Spin size="large" />
          </div>
        ) : documents.length === 0 ? (
          <Alert
            message="暂无文档"
            description="点击上方「导入文本」或「导入文件」按钮，上传您的知识内容"
            type="info"
            showIcon
          />
        ) : (
          <List
            dataSource={documents}
            renderItem={(doc) => (
              <List.Item
                actions={[
                  <Popconfirm
                    key="delete"
                    title="确认删除此文档？"
                    description={`将删除「${doc.source_name}」及其所有 ${doc.total_chunks} 个块`
                    }
                    onConfirm={() => handleDeleteDocument(doc.doc_id)}
                    okText="删除"
                    cancelText="取消"
                    okButtonProps={{ danger: true }}
                  >
                    <Button danger size="small" icon={<DeleteOutlined />}>
                      删除
                    </Button>
                  </Popconfirm>,
                ]}
              >
                <List.Item.Meta
                  avatar={<FileTextOutlined style={{ fontSize: 24, color: '#1890ff' }} />}
                  title={<Text strong>{doc.source_name}</Text>}
                  description={
                    <Space>
                      <Tag color="blue">{doc.total_chunks} 个块</Tag>
                      <Text type="secondary" style={{ fontSize: 12 }}>ID: {doc.doc_id}</Text>
                    </Space>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </Card>

      {/* 导入模态框 */}
      <Modal
        title={importType === 'text' ? '导入文本' : '导入文件'}
        open={importModalVisible}
        onCancel={() => setImportModalVisible(false)}
        footer={null}
        width={640}
      >
        {importType === 'text' ? (
          <Form form={textForm} layout="vertical" onFinish={handleTextImport}>
            <Form.Item
              label="来源名称"
              name="source_name"
              rules={[{ required: true, message: '请输入来源名称' }]}
              tooltip="用于标识此文本来源，如文件名、文档标题或 SQL 文件名"
            >
              <Input placeholder="例如：数据仓库设计规范 v2.1" />
            </Form.Item>

            <Form.Item
              label="文本内容"
              name="text"
              rules={[{ required: true, message: '请输入文本内容' }]}
            >
              <TextArea rows={8} placeholder="请粘贴要导入的文本内容..." />
            </Form.Item>

            <Divider>分块设置</Divider>

            <Space size="large" style={{ display: 'flex' }}>
              <Form.Item label="目标块大小（字符）" name="chunk_size" initialValue={500}>
                <InputNumber min={50} max={2000} step={50} />
              </Form.Item>
              <Form.Item label="块重叠（字符）" name="chunk_overlap" initialValue={50}>
                <InputNumber min={0} max={200} step={10} />
              </Form.Item>
            </Space>

            <Form.Item
              label="自定义分隔符"
              name="custom_separators"
              tooltip="手动输入分隔符并回车确认（每个分隔符回车一次；支持逗号、句号、换行符等）；留空使用默认分段"
            >
              <Select
                mode="tags"
                placeholder="输入分隔符后回车确认（可多个，支持逗号、换行符等）"
                allowClear
              />
            </Form.Item>

            {importing && (
              <Progress percent={importProgress} status="active" style={{ marginBottom: 16 }} />
            )}

            {importResult && (
              <Alert
                message={`导入成功！共生成 ${importResult.total_chunks} 个块`}
                description={
                  <div>
                    <Text>已写入向量数据库：{importResult.added_to_vector_db} 个</Text>
                    <div style={{ marginTop: 8 }}>
                      <Text type="secondary" style={{ fontSize: 12 }}>分块预览：</Text>
                      <List
                        size="small"
                        dataSource={importResult.chunks.slice(0, 3)}
                        renderItem={(chunk) => (
                          <List.Item style={{ padding: '4px 0' }}>
                            <Text code style={{ fontSize: 11 }}>
                              [{chunk.chunk_index + 1}/{chunk.total_chunks}] {chunk.content_preview}
                            </Text>
                          </List.Item>
                        )}
                      />
                      {importResult.chunks.length > 3 && (
                        <Text type="secondary" style={{ fontSize: 11 }}>
                          ... 还有 {importResult.chunks.length - 3} 个块
                        </Text>
                      )}
                    </div>
                  </div>
                }
                type="success"
                style={{ marginBottom: 16 }}
              />
            )}

            <Form.Item>
              <Space>
                <Button type="primary" htmlType="submit" loading={importing} icon={<PlusOutlined />}>
                  开始导入
                </Button>
                <Button onClick={() => setImportModalVisible(false)}>
                  {importResult ? '关闭' : '取消'}
                </Button>
              </Space>
            </Form.Item>
          </Form>
        ) : (
          <div>
            {/* 分块参数 */}
            <Space size="large" style={{ marginBottom: 12 }} align="start">
              <Form.Item label="块大小" style={{ marginBottom: 0 }}>
                <InputNumber
                  min={50}
                  max={2000}
                  step={50}
                  value={fileChunkSize}
                  onChange={(val) => setFileChunkSize(val ?? 500)}
                />
              </Form.Item>
              <Form.Item label="重叠" style={{ marginBottom: 0 }}>
                <InputNumber
                  min={0}
                  max={200}
                  step={10}
                  value={fileChunkOverlap}
                  onChange={(val) => setFileChunkOverlap(val ?? 50)}
                />
              </Form.Item>
              <Form.Item label="分隔符" style={{ marginBottom: 0 }}>
                <Select
                  mode="tags"
                  placeholder="输入分隔符后回车"
                  allowClear
                  style={{ minWidth: 180 }}
                  value={fileSeparators}
                  onChange={(val) => setFileSeparators(val as string[])}
                />
              </Form.Item>
            </Space>

            <Dragger
              accept=".txt,.md,.csv,.sql"
              customRequest={(options: any) => {
                const { file, onSuccess, onError } = options
                handleFileImport(
                  file as File,
                  fileChunkSize,
                  fileChunkOverlap,
                  fileSeparators,
                )
                  .then(() => onSuccess())
                  .catch((err: any) => onError(err))
                return { abort() {} }
              }}
              showUploadList={false}
              disabled={importing}
            >
              <p className="ant-upload-drag-icon">
                <UploadOutlined style={{ fontSize: 48, color: '#1890ff' }} />
              </p>
              <p className="ant-upload-text">点击或拖拽上传文本文件</p>
              <p className="ant-upload-hint">
                支持 .txt、.md、.csv、.sql 格式，上传后自动分块写入向量数据库
              </p>
            </Dragger>

            {importing && (
              <div style={{ marginTop: 16 }}>
                <Text>正在导入并分块...</Text>
                <Progress percent={importProgress} status="active" />
              </div>
            )}

            {importResult && (
              <Alert
                message={`导入成功！共生成 ${importResult.total_chunks} 个块`}
                description={`文档「${importResult.source_name}」已写入向量数据库`}
                type="success"
                style={{ marginTop: 16 }}
              />
            )}
          </div>
        )}
      </Modal>

      {/* 搜索模态框 */}
      <Modal
        title="知识库检索"
        open={searchVisible}
        onCancel={() => setSearchVisible(false)}
        footer={null}
        width={720}
      >
        <Form form={searchForm} layout="inline" onFinish={handleSearch} style={{ marginBottom: 16 }}>
          <Form.Item name="query" rules={[{ required: true, message: '请输入查询内容' }]} style={{ flex: 1 }}>
            <Input placeholder="输入查询内容，如：如何设计 DWD 层表？" size="large" />
          </Form.Item>
          <Form.Item name="top_k" initialValue={5}>
            <InputNumber min={1} max={20} placeholder="返回数量" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={searching} icon={<SearchOutlined />}>
              检索
            </Button>
          </Form.Item>
        </Form>

        {searchResults.length > 0 ? (
          <List
            dataSource={searchResults}
            renderItem={(result, index) => (
              <List.Item>
                <List.Item.Meta
                  title={
                    <Space>
                      <Tag color="green">#{index + 1}</Tag>
                      <Text strong>相似度：{(result.score * 100).toFixed(1)}%</Text>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        来源：{result.metadata?.source_name || '未知'}
                      </Text>
                    </Space>
                  }
                  description={
                    <div>
                      <Paragraph
                        ellipsis={{ rows: 3, expandable: true, symbol: '展开' }}
                        style={{ fontSize: 13 }}
                      >
                        {result.content}
                      </Paragraph>
                    </div>
                  }
                />
              </List.Item>
            )}
          />
        ) : (
          !searching && <Empty description="输入查询内容开始检索" />
        )}
      </Modal>
    </div>
  )

  // ==================== 主渲染 ====================

  return (
    <div>
      <Title level={3}>知识库管理</Title>

      {renderKnowledgeSection()}
    </div>
  )
}

export default Editor
