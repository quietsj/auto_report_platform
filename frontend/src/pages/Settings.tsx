import { Card, Typography, Form, Input, Button, message } from 'antd'
import { useEffect } from 'react'

const { Title } = Typography

const STORAGE_KEY = 'ai_auto_etl_settings'

const Settings = () => {
  const [form] = Form.useForm()

  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      try {
        const settings = JSON.parse(saved)
        form.setFieldsValue(settings)
      } catch {
        // Ignore parsing error
      }
    }
  }, [form])

  const handleSave = async () => {
    try {
      const values = await form.validateFields()
      localStorage.setItem(STORAGE_KEY, JSON.stringify(values))
      message.success('设置已保存')
    } catch {
      message.error('请检查输入')
    }
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
          <Form.Item
            label="ChromaDB 地址"
            name="chroma_url"
            initialValue="http://localhost:8033"
          >
            <Input placeholder="http://localhost:8033" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" onClick={handleSave}>
              保存设置
            </Button>
          </Form.Item>
        </Form>
      </Card>

      <Card title="说明">
        <ul>
          <li>配置信息保存在浏览器 localStorage 中</li>
          <li>确保后端服务已启动，默认端口为 8000</li>
          <li>确保 ChromaDB 服务已启动，默认端口为 8033</li>
        </ul>
      </Card>
    </div>
  )
}

export default Settings
