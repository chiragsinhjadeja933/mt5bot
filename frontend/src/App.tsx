import { BrowserRouter, Routes, Route, NavLink, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  LayoutDashboard, TrendingUp, History, Settings2,
  Shield, FileText, Activity, FlaskConical
} from 'lucide-react'

import { useWebSocket } from './hooks/useWebSocket'
import GlobalHeader from './components/GlobalHeader'
import Dashboard from './pages/Dashboard'
import Positions from './pages/Positions'
import HistoryPage from './pages/HistoryPage'
import StrategyPage from './pages/StrategyPage'
import RiskPage from './pages/RiskPage'
import LogsPage from './pages/LogsPage'
import SettingsPage from './pages/SettingsPage'
import ConnectionTestPage from './pages/ConnectionTestPage'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 2, refetchInterval: 2000 } }
})

const NAV_ITEMS = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/positions', icon: TrendingUp, label: 'Positions' },
  { to: '/history', icon: History, label: 'History' },
  { to: '/strategy', icon: Activity, label: 'Strategy' },
  { to: '/risk', icon: Shield, label: 'Risk' },
  { to: '/logs', icon: FileText, label: 'Logs' },
  { to: '/connection-test', icon: FlaskConical, label: 'Connection Test' },
  { to: '/settings', icon: Settings2, label: 'Settings' },
]

import { useEffect } from 'react'
import { getAccount, getXAUUSD, getPositions, getMT5Status } from './services/api'
import { useStore } from './store/useStore'

function AppInner() {
  useWebSocket()

  useEffect(() => {
    async function syncData() {
      try {
        const [accRes, tickRes, posRes, statusRes] = await Promise.all([
          getAccount().catch(() => null),
          getXAUUSD().catch(() => null),
          getPositions().catch(() => null),
          getMT5Status().catch(() => null),
        ])
        if (accRes?.data) useStore.getState().setAccount(accRes.data)
        if (tickRes?.data) useStore.getState().setTick(tickRes.data)
        if (posRes?.data) useStore.getState().setPositions(posRes.data)
        if (statusRes?.data?.connected) {
          useStore.getState().setConnected(true)
          if (statusRes.data.state) {
            useStore.getState().setSystemState({
              ...useStore.getState().systemState,
              connection_state: 'CONNECTED',
            })
          }
        }
      } catch { /* ignore */ }
    }
    syncData()
    const t = setInterval(syncData, 2500)
    return () => clearInterval(t)
  }, [])

  return (
    <>
      <GlobalHeader />
      <div className="app-layout">
        {/* Sidebar nav */}
        <nav className="sidebar">
          {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
            <NavLink key={to} to={to}
              className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
              <Icon size={16} />
              <span className="nav-tooltip">{label}</span>
            </NavLink>
          ))}
        </nav>
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/positions" element={<Positions />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/strategy" element={<StrategyPage />} />
            <Route path="/risk" element={<RiskPage />} />
            <Route path="/logs" element={<LogsPage />} />
            <Route path="/connection-test" element={<ConnectionTestPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </main>
      </div>
    </>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppInner />
      </BrowserRouter>
    </QueryClientProvider>
  )
}
