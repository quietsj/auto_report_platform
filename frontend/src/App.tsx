import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import MainLayout from './components/layout/MainLayout'
import Dashboard from './pages/Dashboard'
import Editor from './pages/Editor'
import Settings from './pages/Settings'
import Workflow from './pages/Workflow'
import Report from './pages/Report'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'

function App() {
  return (
    <ConfigProvider locale={zhCN}>
      <Router>
        <Routes>
          <Route path="/" element={<MainLayout />}>
            <Route path="chat" element={<Dashboard />} />
            <Route index element={<Navigate to="/report" replace />} />
            <Route path="workflow" element={<Workflow />} />
            <Route path="editor" element={<Editor />} />
            <Route path="report" element={<Report />} />
            <Route path="settings" element={<Settings />} />
          </Route>
        </Routes>
      </Router>
    </ConfigProvider>
  )
}

export default App
