import axios from 'axios'

const TOKEN = import.meta.env.VITE_API_TOKEN || 'dev'

export const api = axios.create({
  baseURL: '/api',
  headers: { Authorization: `Bearer ${TOKEN}` },
})

export const connectMT5 = () => api.post('/mt5/connect')
export const disconnectMT5 = () => api.post('/mt5/disconnect')
export const getMT5Status = () => api.get('/mt5/status')
export const runConnectionTest = () => api.post('/mt5/test')
export const getLatestTest = () => api.get('/mt5/test/latest')

export const getAccount = () => api.get('/account')
export const getXAUUSD = () => api.get('/market/xauusd')
export const getPositions = () => api.get('/positions')
export const getOrders = () => api.get('/orders')
export const getHistory = (params?: object) => api.get('/history', { params })

export const startBot = (token: string) => api.post('/trading/start', { confirmation_token: token })
export const pauseBot = () => api.post('/trading/pause')
export const stopBot = () => api.post('/trading/stop')
export const emergencyStop = () => api.post('/trading/emergency-stop')
export const closeAll = () => api.post('/trading/close-all')
export const closePosition = (ticket: number) => api.post(`/positions/${ticket}/close`)

export const getStrategy = () => api.get('/strategy')
export const updateStrategy = (config: object) => api.post('/strategy', config)
export const getExposurePreview = () => api.get('/strategy/exposure-preview')

export const getRisk = () => api.get('/risk')
export const updateRisk = (config: object) => api.put('/risk', config)

export const getLogs = (params?: object) => api.get('/logs', { params })
