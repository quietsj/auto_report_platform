import { Card, Typography, Button, Form, Input, Space, message, List, Spin, Alert, Modal } from 'antd'
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons'
import { useEffect, useState } from 'react'
import api from '../services/api'

const { Title, Text } = Typography
const { TextArea } = Input

interface SchemaItem {
  table_name: string
  schema_info: string
  metadata?: Record<string, any>
}

const Editor = () => {
  const [form] = Form.useForm()
  const [schemas, setSchemas] = useState<SchemaItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string>('')

  const fetchSchemas = async () => {
    setLoading(true)
    try {
      const response = await api.get('/schema/list')
      setSchemas(response.data.data || [])
    } catch (err: any) {
      setError(err.response?.data?.detail || '获取 Schema 列表失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchSchemas()
  }, [])

  const handleAddSchema = async (values: any) => {
    try {
      // 解析 metadata JSON
      let metadata = null
      if (values.metadata_str) {
        try {
          metadata = JSON.parse(values.metadata_str)
        } catch {
          message.error('Metadata 格式错误，请输入有效的 JSON')
          return
        }
      }
      
      await api.post('/schema/add', {
        table_name: values.table_name,
        schema_info: values.schema_info,
        metadata
      })
      message.success('Schema 添加成功')
      form.resetFields()
      fetchSchemas()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '添加失败')
    }
  }

  const handleDelete = (tableName: string) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除表 ${tableName} 吗？`,
      onOk: async () => {
        try {
          await api.delete(`/schema/delete/${tableName}`)
          message.success('删除成功')
          fetchSchemas()
        } catch (err: any) {
          message.error(err.response?.data?.detail || '删除失败')
        }
      }
    })
  }

  return (
    <div>
      <Title level={3}>Schema 管理</Title>
      
      <Card title="添加表结构" style={{ marginBottom: 24 }}>
        <Form
          form={form}
          layout="vertical"
          onFinish={handleAddSchema}
        >
          <Form.Item
            label="表名"
            name="table_name"
            rules={[{ required: true, message: '请输入表名' }]}
          >
            <Input placeholder="例如：dwd_order_detail" />
          </Form.Item>
          <Form.Item
            label="表结构信息"
            name="schema_info"
            rules={[{ required: true, message: '请输入表结构信息' }]}
          >
            <TextArea
              rows={10}
              placeholder="例如：
表名：dwd_order_detail
字段：
- order_id: string, 订单ID
- user_id: string, 用户ID
- category_id: string, 品类ID
- gmv: decimal, 交易金额
- dt: string, 日期分区"
            />
          </Form.Item>
          <Form.Item
            label="元数据 (JSON 格式，可选)"
            name="metadata_str"
            help='例如：{"database": "maxcompute", "owner": "data_team"}'
          >
            <TextArea
              rows={3}
              placeholder='{"database": "maxcompute", "owner": "data_team"}'
            />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" icon={<PlusOutlined />}>
                添加 Schema
              </Button>
              <Button onClick={() => fetchSchemas()}>刷新列表</Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>

      <Card title="已添加的 Schema">
        {error && <Alert message={error} type="error" closable style={{ marginBottom: 16 }} />}
        
        {loading ? (
          <div style={{ textAlign: 'center', padding: 40 }}>
            <Spin size="large" />
          </div>
        ) : schemas.length === 0 ? (
          <Alert message="暂无 Schema" description="请先添加表结构" type="info" />
        ) : (
          <List
            dataSource={schemas}
            renderItem={(item) => (
              <List.Item
                actions={[
                  <Button danger icon={<DeleteOutlined />} onClick={() => handleDelete(item.table_name)}>
                    删除
                  </Button>
                ]}
              >
                <List.Item.Meta
                  title={<Text strong>{item.table_name}</Text>}
                  description={
                    <div>
                      <Text ellipsis={{ rows: 2, expandable: true }}>
                        {item.schema_info}
                      </Text>
                      {item.metadata && Object.keys(item.metadata).length > 0 && (
                        <div style={{ marginTop: 8 }}>
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            元数据: {JSON.stringify(item.metadata)}
                          </Text>
                        </div>
                      )}
                    </div>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </Card>
    </div>
  )
}

export default Editor
