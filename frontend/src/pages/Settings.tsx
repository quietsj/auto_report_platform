import { Card, Typography, Form, Input, Button, message } from 'antd'

const { Title } = Typography

const Settings = () => {
  const [form] = Form.useForm()

  const handleSave = () => {
    message.success('设置已保存')
  }

  return (
    <div>
      <Title level={3}>系统设置</Title>
      
      <Card title="API 配置" style={{ marginBottom: 24 }}>
        <Form form={form} layout="vertical">
          <Form.Item
            label="LiteLLM API 地址"
            name="litellm_api_base"
            initialValue="http://localhost:4000"
          >
            <Input placeholder="http://localhost:4000" />
          </Form.Item>
          <Form.Item
            label="Embedding 服务地址"
            name="embedding_service_url"
            initialValue="http://localhost:8001"
          >
            <Input placeholder="http://localhost:8001" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" onClick={handleSave}>
              保存设置
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  )
}

export default Settings
