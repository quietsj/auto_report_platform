import { Card, Typography, Button, Form, Input, Space, message } from 'antd'
import api from '../services/api'

const { Title } = Typography
const { TextArea } = Input

const Editor = () => {
  const [form] = Form.useForm()

  const handleAddSchema = async (values: any) => {
    try {
      await api.post('/schema/add', values)
      message.success('Schema 添加成功')
      form.resetFields()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '添加失败')
    }
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
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">
                添加 Schema
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>
    </div>
  )
}

export default Editor
