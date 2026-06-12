import axios, { AxiosRequestConfig } from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 300000, // 全局超时 5 分钟，避免 AI 生成链路超时
})

// 请求拦截器：对慢接口设置更长的超时
api.interceptors.request.use((config: AxiosRequestConfig) => {
  const url = config.url || ''
  const slowEndpoints = [
    '/chat/pipeline',
    '/knowledge/import/file',
  ]
  if (slowEndpoints.some((ep) => url.includes(ep))) {
    config.timeout = 600000 // 慢接口单独 10 分钟
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error)
    // 对超时错误做友好提示
    if (error?.code === 'ECONNABORTED' || error?.message?.includes('timeout')) {
      return Promise.reject(new Error('请求超时，请重试或检查网络'))
    }
    return Promise.reject(error)
  },
)

export default api
