import { useState, useRef, useEffect } from 'react'
import { Card, Input, Button, Row, Col, Typography, Alert, Avatar, List, Divider } from 'antd'
import { SendOutlined, UserOutlined, RobotOutlined } from '@ant-design/icons'
import api from '../services/api'

const { Title, Paragraph, Text } = Typography
const { TextArea } = Input

interface Message {
  id: string
  type: 'user' | 'ai'
  content: string
  sql?: string
  intent?: string
  timestamp: Date
}

const Dashboard = () => {
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [messages, setMessages] = useState<Message[]>([])
  const [error, setError] = useState<string>('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async () => {
    if (!input.trim()) return
    
    const userMessage: Message = {
      id: Date.now().toString(),
      type: 'user',
      content: input,
      timestamp: new Date(),
    }
    
    setMessages(prev => [...prev, userMessage])
    const userInput = input
    setInput('')
    setLoading(true)
    setError('')

    try {
      const response = await api.post('/etl/generate', { query: userInput })
      
      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: 'ai',
        content: '我来帮您生成查询...',
        intent: response.data.intent,
        sql: response.data.sql,
        timestamp: new Date(),
      }
      
      setMessages(prev => [...prev, aiMessage])
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || '请求失败')
    } finally {
      setLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div style={{ height: '80vh', display: 'flex', flexDirection: 'column' }}>
      <Title level={3}>对话开发</Title>
      <Paragraph>
        用自然语言描述您的需求，我来帮您生成查询
      </Paragraph>

      {error && (
        <Alert
          message="出错了"
          description={error}
          type="error"
          closable
          onClose={() => setError('')}
          style={{ marginBottom: 16 }}
        />
      )}

      <div 
        style={{ 
          flex: 1, 
          overflow: 'auto', 
          marginBottom: 16, 
          padding: 16,
          background: '#f5f5f5',
          borderRadius: 8,
        }}
      >
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <Paragraph>
              👋 您好！我是AI助手，请告诉我您想分析什么数据？
            </Paragraph>
            <Paragraph type="secondary">
              例如：分析上个月各品类的GMV，看看哪个增长最快
            </Paragraph>
          </div>
        )}

        <List
          dataSource={messages}
          renderItem={(msg) => (
            <div
              style={{
                display: 'flex',
                justifyContent: msg.type === 'user' ? 'flex-end' : 'flex-start',
                marginBottom: 24,
              }}
            >
              <div style={{ display: 'flex', flexDirection: msg.type === 'user' ? 'row-reverse' : 'row' }}>
                <Avatar 
                  icon={msg.type === 'user' ? <UserOutlined /> : <RobotOutlined />}
                  style={{ 
                    marginLeft: msg.type === 'user' ? 12 : 0, marginRight: msg.type === 'ai' ? 12 : 0 }}
                />
                <div style={{ maxWidth: '70%' }}>
                  <Card size="small" style={{ background: msg.type === 'user' ? '#e6f7ff' : '#f6ffed' }}>
                  {msg.type === 'user' ? (
                    <Text>{msg.content}</Text>
                  ) : (
                    <div>
                      {msg.intent && (
                        <div style={{ marginBottom: 16 }}>
                          <Title level={5}>意图解析</Title>
                          <Paragraph>{msg.intent}</Paragraph>
                        </div>
                      )}
                      
                      {msg.sql && (
                        <div>
                          <Title level={5}>生成的 SQL</Title>
                          <pre style={{ 
                            background: '#fff', 
                            padding: 12, 
                            borderRadius: 4,
                            overflow: 'auto',
                            border: '1px solid #d9d9d9',
                          }}>
                            {msg.sql}
                          </pre>
                        </div>
                      )}
                    </div>
                  )}
                  </Card>
                  <div style={{ 
                    fontSize: 12, color: '#999', marginTop: 4, textAlign: msg.type === 'user' ? 'right' : 'left' }}>
                    {msg.timestamp.toLocaleTimeString()}
                  </div>
                </div>
              </div>
            </div>
          )}
        />
        <div ref={messagesEndRef} />
      </div>

      <Divider style={{ margin: '16px 0' }} />

      <Card>
        <Row gutter={16} style={{ alignItems: 'flex-end' }}>
          <Col flex={20}>
            <TextArea
              rows={3}
              placeholder="请输入您的需求..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onPressEnter={handleKeyPress}
              disabled={loading}
            />
          </Col>
          <Col flex={4}>
            <Button
              type="primary"
              icon={<SendOutlined />}
              onClick={handleSend}
              loading={loading}
              size="large"
              block
            >
              发送
            </Button>
          </Col>
        </Row>
      </Card>
    </div>
  )
}

export default Dashboard
