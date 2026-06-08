import { useState } from 'react'
import { Card, Input, Button, Row, Col, Typography, Spin, Alert } from 'antd'
import { SendOutlined } from '@ant-design/icons'
import api from '../services/api'

const { Title, Paragraph, Text } = Typography
const { TextArea } = Input

const Dashboard = () => {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState<string>('')

  const handleSubmit = async () => {
    if (!query.trim()) return
    setLoading(true)
    setError('')
    try {
      const response = await api.post('/etl/generate', { query })
      setResult(response.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <Title level={3}>自然语言查询</Title>
      <Paragraph>
        输入您的数据分析需求，AI 将自动解析意图并生成相应的 SQL
      </Paragraph>
      
      <Card style={{ marginBottom: 24 }}>
        <TextArea
          rows={4}
          placeholder="例如：分析上个月各品类的 GMV，看看哪个增长最快"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{ marginBottom: 16 }}
        />
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={handleSubmit}
          loading={loading}
          size="large"
        >
          生成分析
        </Button>
      </Card>

      {error && (
        <Alert
          message="出错了"
          description={error}
          type="error"
          closable
          style={{ marginBottom: 24 }}
        />
      )}

      {loading && (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin size="large" tip="正在分析您的需求..." />
        </div>
      )}

      {result && result.success && (
        <Row gutter={[16, 16]}>
          <Col xs={24} lg={12}>
            <Card title="意图解析">
              <pre style={{ whiteSpace: 'pre-wrap' }}>{result.intent}</pre>
            </Card>
          </Col>
          <Col xs={24} lg={12}>
            <Card title="生成的 SQL">
              <pre style={{ whiteSpace: 'pre-wrap', background: '#f5f5f5', padding: 12, borderRadius: 4 }}>
                {result.sql}
              </pre>
            </Card>
          </Col>
        </Row>
      )}
    </div>
  )
}

export default Dashboard
