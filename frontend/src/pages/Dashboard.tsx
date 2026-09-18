import { useStore } from '../store/useStore'

import { startBot, emergencyStop, pauseBot, stopBot } from '../services/api'
import { Activity, TrendingUp, AlertTriangle } from 'lucide-react'
import { useState } from 'react'

export default function Dashboard() {
  const { account, tick, positions, systemState } = useStore()
  const [startToken, setStartToken] = useState('')
  const [showStart, setShowStart] = useState(false)

  const pnlNum = Number(account?.profit || 0)
  const equity = Number(account?.equity || 0)
  const balance = Number(account?.balance || 0)
  const marginLevel = Number(account?.margin_level || 0)
  const currency = account?.currency || 'USD'

  const botState = systemState.bot_state
  const isRunning = botState === 'RUNNING'
  const isPaused = botState === 'PAUSED'
  const isEmergency = botState === 'EMERGENCY_STOP'

  const handleStart = async () => {
    if (startToken.trim().toUpperCase() !== 'START DEMO') {
      alert("Type exactly 'START DEMO' to confirm")
      return
    }
    try {
      await startBot(startToken)
      setShowStart(false)
      setStartToken('')
    } catch (e: any) {
      alert('Start failed: ' + (e.response?.data?.detail || e.message))
    }
  }

  return (
    <div style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 10, height: '100%' }}>

      {/* Account Stats */}
      <div className="stat-grid">
        <div className="stat-box">
          <div className="stat-label">Balance</div>
          <div className={`stat-value ${equity >= balance ? 'profit' : 'loss'}`}>
            {balance.toFixed(2)}
          </div>
          <div className="stat-sub">{currency}</div>
        </div>
        <div className="stat-box">
          <div className="stat-label">Equity</div>
          <div className={`stat-value ${equity >= balance ? 'profit' : 'loss'}`}>
            {equity.toFixed(2)}
          </div>
          <div className="stat-sub">{currency}</div>
        </div>
        <div className="stat-box">
          <div className="stat-label">Floating P/L</div>
          <div className={`stat-value ${pnlNum >= 0 ? 'profit' : 'loss'}`}>
            {pnlNum >= 0 ? '+' : ''}{pnlNum.toFixed(2)}
          </div>
          <div className="stat-sub" style={{ fontSize: 9, color: 'var(--text-muted)' }}>Provenance: MT5</div>
        </div>
        <div className="stat-box">
          <div className="stat-label">Free Margin</div>
          <div className="stat-value">{Number(account?.free_margin || 0).toFixed(2)}</div>
          <div className="stat-sub">{currency}</div>
        </div>
        <div className="stat-box">
          <div className="stat-label">Margin Level</div>
          <div className={`stat-value ${marginLevel > 200 ? 'profit' : marginLevel > 150 ? 'neutral' : 'loss'}`}>
            {marginLevel > 0 ? `${marginLevel.toFixed(1)}%` : '∞'}
          </div>
        </div>
        <div className="stat-box">
          <div className="stat-label">Leverage</div>
          <div className="stat-value">1:{account?.leverage || '—'}</div>
        </div>
        <div className="stat-box">
          <div className="stat-label">Account Type</div>
          <div style={{ marginTop: 4 }}>
            <span className="badge badge-green">{account?.trade_mode_name || 'DEMO'}</span>
          </div>
        </div>
        <div className="stat-box">
          <div className="stat-label">Mode</div>
          <div style={{ marginTop: 4 }}>
            <span className={`badge ${systemState.execution_mode === 'DRY_RUN' ? 'badge-yellow' : 'badge-blue'}`}>
              {systemState.execution_mode}
            </span>
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 260px', gap: 10, flex: 1 }}>

        {/* Left: Market + Positions */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>

          {/* XAUUSD Market Card */}
          <div className="card">
            <div className="card-header">
              <TrendingUp size={12} /> XAUUSD Market Data
            </div>
            <div className="card-body">
              {tick ? (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
                  <div>
                    <div className="stat-label">Bid</div>
                    <div className="mono loss" style={{ fontSize: 16, fontWeight: 700 }}>
                      {Number(tick.bid).toFixed(2)}
                    </div>
                  </div>
                  <div>
                    <div className="stat-label">Ask</div>
                    <div className="mono profit" style={{ fontSize: 16, fontWeight: 700 }}>
                      {Number(tick.ask).toFixed(2)}
                    </div>
                  </div>
                  <div>
                    <div className="stat-label">Spread</div>
                    <div className="mono" style={{ fontSize: 14 }}>
                      {tick.spread_points} pts
                    </div>
                  </div>
                  <div>
                    <div className="stat-label">Tick Age</div>
                    <div className={`mono ${(tick.age_ms || 0) > 3000 ? 'loss' : 'neutral'}`} style={{ fontSize: 14 }}>
                      {Math.round(tick.age_ms || 0)}ms
                      {tick.is_stale && <span className="stale-badge" style={{ marginLeft: 4 }}>STALE</span>}
                    </div>
                  </div>
                </div>
              ) : (
                <span style={{ color: 'var(--text-muted)' }}>No market data — connect MT5</span>
              )}
            </div>
          </div>

          {/* Open Positions */}
          <div className="card" style={{ flex: 1, overflow: 'auto' }}>
            <div className="card-header">
              <Activity size={12} />
              Open Positions ({positions.length})
            </div>
            <div style={{ overflow: 'auto' }}>
              {positions.length === 0 ? (
                <div style={{ padding: 20, color: 'var(--text-muted)', textAlign: 'center' }}>
                  No open positions
                </div>
              ) : (
                <table>
                  <thead>
                    <tr>
                      <th>Ticket</th><th>Dir</th><th>Vol</th>
                      <th>Entry</th><th>Current</th><th>P/L</th>
                      <th>Swap</th><th>SL</th><th>TP</th><th>Magic</th>
                    </tr>
                  </thead>
                  <tbody>
                    {positions.map((p) => {
                      const pnl = Number(p.profit)
                      return (
                        <tr key={p.ticket}>
                          <td className="mono" style={{ color: 'var(--accent)' }}>{p.ticket}</td>
                          <td>
                            <span className={`badge ${p.direction === 'BUY' ? 'badge-green' : 'badge-red'}`}>
                              {p.direction}
                            </span>
                          </td>
                          <td className="mono">{p.volume}</td>
                          <td className="mono">{Number(p.price_open).toFixed(2)}</td>
                          <td className="mono">{Number(p.price_current).toFixed(2)}</td>
                          <td className={`mono ${pnl >= 0 ? 'profit' : 'loss'}`}>
                            {pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}
                          </td>
                          <td className="mono">{Number(p.swap).toFixed(2)}</td>
                          <td className="mono">{Number(p.sl).toFixed(2)}</td>
                          <td className="mono">{Number(p.tp).toFixed(2)}</td>
                          <td className="mono" style={{ color: 'var(--text-muted)' }}>{p.magic}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>

        {/* Right: Bot Control Panel */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div className="card">
            <div className="card-header"><Activity size={12} /> Bot Status</div>
            <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>

              <div style={{ textAlign: 'center' }}>
                <span className={`badge ${isRunning ? 'badge-green' : isPaused ? 'badge-yellow' : isEmergency ? 'badge-red' : 'badge-muted'}`}
                  style={{ fontSize: 12, padding: '4px 12px' }}>
                  {botState}
                </span>
              </div>

              <div>
                <div className="stat-label">Mode</div>
                <span className={`badge ${systemState.execution_mode === 'DRY_RUN' ? 'badge-yellow' : 'badge-blue'}`}>
                  {systemState.execution_mode}
                </span>
              </div>

              <div>
                <div className="stat-label">Positions</div>
                <div style={{ fontSize: 20, fontWeight: 700 }}>{positions.length}</div>
              </div>

              <div>
                <div className="stat-label">Total Floating P/L</div>
                <div className={`mono ${pnlNum >= 0 ? 'profit' : 'loss'}`} style={{ fontSize: 16, fontWeight: 700 }}>
                  {pnlNum >= 0 ? '+' : ''}{pnlNum.toFixed(2)} {currency}
                </div>
                <div style={{ fontSize: 9, color: 'var(--text-muted)' }}>Provenance: MT5</div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
                {!isRunning && !isPaused && !isEmergency && (
                  <>
                    {!showStart ? (
                      <button className="btn btn-success" style={{ width: '100%' }}
                        onClick={() => setShowStart(true)}>
                        START BOT
                      </button>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                        <div className="alert alert-warning">
                          Type <strong>START DEMO</strong> to confirm
                        </div>
                        <input value={startToken} onChange={e => setStartToken(e.target.value)}
                          placeholder="START DEMO" />
                        <button className="btn btn-success" onClick={handleStart}>Confirm Start</button>
                        <button className="btn btn-ghost" onClick={() => setShowStart(false)}>Cancel</button>
                      </div>
                    )}
                  </>
                )}

                {isRunning && (
                  <button className="btn btn-warning" style={{ width: '100%' }} onClick={pauseBot}>
                    ⏸ PAUSE
                  </button>
                )}

                {(isRunning || isPaused) && (
                  <button className="btn btn-ghost" style={{ width: '100%' }} onClick={stopBot}>
                    ⏹ STOP
                  </button>
                )}

                <button className="btn btn-danger" style={{ width: '100%' }}
                  onClick={() => { if (confirm('EMERGENCY STOP?')) emergencyStop() }}>
                  <AlertTriangle size={14} /> EMERGENCY STOP
                </button>
              </div>
            </div>
          </div>

          {/* Connection info */}
          {account && (
            <div className="card">
              <div className="card-header">Connection</div>
              <div className="card-body" style={{ fontSize: 11 }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <div><span style={{ color: 'var(--text-muted)' }}>Login: </span>{account.login}</div>
                  <div><span style={{ color: 'var(--text-muted)' }}>Server: </span>{account.server}</div>
                  <div><span style={{ color: 'var(--text-muted)' }}>Margin: </span>{account.margin_mode_name}</div>
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>Type: </span>
                    <span className="badge badge-green">{account.trade_mode_name}</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Risk Disclosure */}
      <div style={{ background: 'var(--yellow-dim)', border: '1px solid var(--yellow)', borderRadius: 6,
        padding: '6px 12px', fontSize: 10, color: 'var(--yellow)' }}>
        ⚠ <strong>RISK DISCLOSURE:</strong> For educational/demo use only. Grid strategies can produce very large losses in a single adverse move. Demo results do not reflect live conditions.
      </div>
    </div>
  )
}
