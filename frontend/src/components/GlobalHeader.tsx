import { useStore } from '../store/useStore'
import { emergencyStop, connectMT5, closeAll, pauseBot } from '../services/api'
import { Wifi, AlertTriangle, Pause, Square } from 'lucide-react'

export default function GlobalHeader() {
  const { systemState, account, tick, wsStatus } = useStore()

  const connState = systemState.connection_state
  const botState = systemState.bot_state
  const mode = systemState.execution_mode
  const isEmergency = botState === 'EMERGENCY_STOP'
  const isDryRun = mode === 'DRY_RUN'

  const connDotClass =
    connState === 'CONNECTED' ? 'connected' :
    connState === 'CONNECTING' ? 'connecting' : 'disconnected'

  const handleConnect = async () => {
    try {
      const res = await connectMT5()
      if (res.data?.status === 'CONNECTED' || res.data?.status === 'ALREADY_CONNECTED') {
        useStore.getState().setConnected(true)
        useStore.getState().setSystemState({
          ...systemState,
          connection_state: 'CONNECTED',
        })
        if (res.data.balance) {
          useStore.getState().setAccount({
            login: res.data.login,
            server: res.data.server,
            currency: res.data.currency,
            balance: res.data.balance,
            equity: res.data.equity,
            leverage: res.data.leverage,
            trade_mode_name: res.data.account_type,
            margin_mode_name: res.data.margin_mode,
          })
        }
      }
    } catch (e: any) {
      alert('Connect failed: ' + (e.response?.data?.detail?.message || e.message))
    }
  }

  const handleEmergency = async () => {
    if (!confirm('⚠ EMERGENCY STOP — stop all bot activity?')) return
    await emergencyStop()
  }

  const handleCloseAll = async () => {
    if (!confirm('Close ALL open positions?')) return
    await closeAll()
  }

  return (
    <>
      {isEmergency && (
        <div className="emergency-banner">
          ⚠ EMERGENCY STOP ACTIVE — All bot entries blocked — Reset required
        </div>
      )}
      <div className="global-header">
        {/* Logo */}
        <span style={{ fontWeight: 800, fontSize: 13, color: 'var(--accent)', marginRight: 8 }}>
          MT5 TERMINAL
        </span>

        {/* Connection status */}
        <span className={`conn-dot ${connDotClass}`} />
        <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
          {connState}
        </span>

        {/* DEMO badge */}
        <span className="badge badge-green">DEMO</span>

        {/* Mode badge */}
        <span className={`badge ${isDryRun ? 'badge-yellow' : 'badge-blue'}`}>
          {isDryRun ? 'DRY RUN' : 'DEMO EXEC'}
        </span>

        {/* Bot state */}
        <span className={`badge ${botState === 'RUNNING' ? 'badge-green' : botState === 'PAUSED' ? 'badge-yellow' : 'badge-muted'}`}>
          {botState}
        </span>

        {/* Account info */}
        {account && (
          <>
            <span style={{ color: 'var(--text-muted)', fontSize: 10 }}>|</span>
            <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)' }}>
              <span style={{ color: 'var(--text-secondary)' }}>BAL </span>
              <span style={{ color: 'var(--text-primary)' }}>
                {Number(account.balance).toFixed(2)} {account.currency}
              </span>
            </span>
            <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)' }}>
              <span style={{ color: 'var(--text-secondary)' }}>EQ </span>
              <span className={Number(account.equity) >= Number(account.balance) ? 'profit' : 'loss'}>
                {Number(account.equity).toFixed(2)}
              </span>
            </span>
          </>
        )}

        {/* XAUUSD price */}
        {tick && (
          <>
            <span style={{ color: 'var(--text-muted)', fontSize: 10 }}>|</span>
            <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--orange)' }}>
              XAUUSD {Number(tick.display_price).toFixed(2)}
            </span>
            {tick.is_stale && <span className="stale-badge">STALE</span>}
            {tick.is_frozen && <span className="stale-badge" style={{ background: 'var(--red-dim)', color: 'var(--red)', borderColor: 'var(--red)' }}>FROZEN</span>}
          </>
        )}

        {/* WS status */}
        <span style={{ marginLeft: 'auto' }} />
        <span style={{ fontSize: 10, color: wsStatus === 'live' ? 'var(--green)' : 'var(--yellow)' }}>
          WS {wsStatus.toUpperCase()}
        </span>

        {/* Action buttons */}
        {connState !== 'CONNECTED' && (
          <button className="btn btn-ghost btn-sm" onClick={handleConnect}>
            <Wifi size={12} /> Connect MT5
          </button>
        )}

        <button className="btn btn-warning btn-sm" onClick={pauseBot} title="Pause bot">
          <Pause size={12} />
        </button>

        <button className="btn btn-ghost btn-sm" onClick={handleCloseAll} title="Close all positions"
          style={{ borderColor: 'var(--red)', color: 'var(--red)' }}>
          <Square size={12} /> CLOSE ALL
        </button>

        <button className="btn btn-danger btn-sm" onClick={handleEmergency}>
          <AlertTriangle size={12} /> EMERGENCY STOP
        </button>
      </div>
    </>
  )
}
