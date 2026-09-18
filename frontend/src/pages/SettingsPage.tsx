import { useState } from 'react'
import { connectMT5, disconnectMT5 } from '../services/api'
import { useStore } from '../store/useStore'

export default function SettingsPage() {
  const { systemState } = useStore()
  const [mode, setMode] = useState('DRY_RUN')
  const [modeToken, setModeToken] = useState('')

  const handleConnect = async () => {
    try { await connectMT5(); alert('Connected!') } catch (e: any) {
      alert('Failed: ' + (e.response?.data?.detail || e.message)) }
  }

  const handleDisconnect = async () => {
    await disconnectMT5()
    alert('Disconnected')
  }

  const handleModeSwitch = async () => {
    if (mode === 'DEMO_EXECUTION' && modeToken.trim().toUpperCase() !== 'DEMO EXECUTION') {
      alert("Type 'DEMO EXECUTION' to switch to demo execution mode")
      return
    }
    const { api } = await import('../services/api')
    await api.post('/trading/mode', { mode, confirmation_token: modeToken })
    alert(`Mode switched to ${mode}`)
  }

  return (
    <div style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 12, maxWidth: 600 }}>

      {/* MT5 Connection */}
      <div className="card">
        <div className="card-header">MT5 Connection</div>
        <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div className="alert alert-info" style={{ fontSize: 11 }}>
            MT5 terminal path, login, password and server are configured in the backend .env file.
            Use these buttons to connect/disconnect at runtime.
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-primary" onClick={handleConnect}>Connect MT5</button>
            <button className="btn btn-ghost" onClick={handleDisconnect}>Disconnect</button>
          </div>
          <div>
            <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Status: </span>
            <span className={`badge ${systemState.connection_state === 'CONNECTED' ? 'badge-green' : 'badge-muted'}`}>
              {systemState.connection_state}
            </span>
          </div>
        </div>
      </div>

      {/* Mode Switch */}
      <div className="card">
        <div className="card-header">Execution Mode</div>
        <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div className="alert alert-warning" style={{ fontSize: 11 }}>
            DRY RUN: Virtual fills, no real orders sent.<br />
            DEMO EXECUTION: Real orders sent to demo account (requires connection test to pass first).
          </div>
          <div>
            <label>Mode</label>
            <select value={mode} onChange={e => setMode(e.target.value)}>
              <option value="DRY_RUN">DRY_RUN</option>
              <option value="DEMO_EXECUTION">DEMO_EXECUTION</option>
            </select>
          </div>
          {mode === 'DEMO_EXECUTION' && (
            <div>
              <label>Type "DEMO EXECUTION" to confirm</label>
              <input value={modeToken} onChange={e => setModeToken(e.target.value)} placeholder="DEMO EXECUTION" />
            </div>
          )}
          <button className="btn btn-primary" onClick={handleModeSwitch}>Switch Mode</button>
        </div>
      </div>

      {/* About */}
      <div className="card">
        <div className="card-header">About</div>
        <div className="card-body" style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
          <div>MT5 Demo Trading Terminal — Version 1.0.0</div>
          <div>Built for demo/educational use only</div>
          <div>Backend: FastAPI + MT5 Python API</div>
          <div>Frontend: React + TypeScript + Vite</div>
          <div style={{ marginTop: 8 }}>
            <span className="badge badge-green">DEMO ONLY</span>
            {' '}All V1 builds enforce DEMO_ONLY=true. Live trading is not supported.
          </div>
        </div>
      </div>

      {/* Risk Disclosure */}
      <div className="alert alert-warning">
        ⚠ <strong>RISK DISCLOSURE:</strong> This software is for educational and demonstration purposes only.
        Trading financial instruments involves substantial risk of loss. Past performance of any algorithm
        does not guarantee future results. Do not use demo results to infer live profitability.
      </div>
    </div>
  )
}
