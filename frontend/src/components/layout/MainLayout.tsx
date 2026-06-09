import { Layout, Menu } from 'antd'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { DashboardOutlined, CodeOutlined, SettingOutlined, ThunderboltOutlined, BarChartOutlined } from '@ant-design/icons'

const { Sider, Content } = Layout

const MainLayout = () => {
  const navigate = useNavigate()
  const location = useLocation()

  const menuItems = [
    {
      key: '/report',
      icon: <BarChartOutlined />,
      label: '报表展示',
    },
    {
      key: '/',
      icon: <DashboardOutlined />,
      label: '对话开发',
    },
    {
      key: '/workflow',
      icon: <ThunderboltOutlined />,
      label: '工作流',
    },
    {
      key: '/editor',
      icon: <CodeOutlined />,
      label: '知识库管理',
    },
    {
      key: '/settings',
      icon: <SettingOutlined />,
      label: '系统设置',
    },
  ]

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider 
        theme="dark" 
        width={240}
        style={{
          overflow: 'auto',
          height: '100vh',
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
        }}
      >
        <div style={{ height: 64, padding: 16, textAlign: 'center', color: 'white', fontWeight: 'bold', fontSize: 18 }}>
          AI Auto-Data-Pipeline
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ height: '100%', borderRight: 0 }}
        />
      </Sider>
      <Layout style={{ marginLeft: 240 }}>
        <Content
          style={{
            margin: 0,
            padding: 24,
            minHeight: '100vh',
            background: '#fff',
          }}
        >
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}

export default MainLayout
