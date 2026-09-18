import { useQuery } from '@tanstack/react-query'
import { getHistory } from '../services/api'
import { useState } from 'react'

export default function HistoryPage() {
  const [symbol, setSymbol] = useState('')
  const [from, setFrom] = useState('')
  const { data: deals = [] } = useQuery({
    queryKey: ['history', symbol, from],
    queryFn: () => getHistory({ symbol: symbol || undefined, from_date: from || undefined }).then(r => r.data),
  })

  const totalNet = deals.reduce((s: number, d: any) => s + Number(d.net_profit || 0), 0)

  return (
    <div style={{ padding: 12 }}>
      <div style={{ display: 'flex', gap: 12, marginBottom: 12, alignItems: 'flex-end' }}>
        <div>
          <label>Symbol</label>
          <input value={symbol} onChange={e => setSymbol(e.target.value)} placeholder="XAUUSD" style={{ width: 120 }} />
        </div>
        <div>
          <label>From Date</label>
          <input type="date" value={from} onChange={e => setFrom(e.target.value)} style={{ width: 140 }} />
        </div>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, paddingBottom: 2 }}>
          Net P/L: <span className={totalNet >= 0 ? 'profit' : 'loss'}>
            {totalNet >= 0 ? '+' : ''}{totalNet.toFixed(2)}
          </span>
          <span style={{ fontSize: 9, color: 'var(--text-muted)', marginLeft: 6 }}>Provenance: MT5</span>
        </div>
      </div>
      <div className="card" style={{ overflow: 'auto' }}>
        <table>
          <thead><tr>
            <th>Ticket</th><th>Position</th><th>Symbol</th>
            <th>Type</th><th>Vol</th><th>Price</th>
            <th>Profit</th><th>Commission</th><th>Swap</th><th>Net</th>
            <th>Reason</th><th>Time</th>
          </tr></thead>
          <tbody>
            {deals.length === 0 && (
              <tr><td colSpan={12} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 24 }}>No history</td></tr>
            )}
            {deals.map((d: any) => {
              const net = Number(d.net_profit || 0)
              return (
                <tr key={d.ticket}>
                  <td className="mono" style={{ color: 'var(--accent)' }}>{d.ticket}</td>
                  <td className="mono">{d.position_id}</td>
                  <td>{d.symbol}</td>
                  <td><span className={`badge ${d.type === 0 ? 'badge-green' : 'badge-red'}`}>{d.type === 0 ? 'BUY' : 'SELL'}</span></td>
                  <td className="mono">{d.volume}</td>
                  <td className="mono">{Number(d.price).toFixed(2)}</td>
                  <td className={`mono ${Number(d.profit) >= 0 ? 'profit' : 'loss'}`}>{Number(d.profit).toFixed(2)}</td>
                  <td className="mono loss">{Number(d.commission).toFixed(2)}</td>
                  <td className="mono">{Number(d.swap).toFixed(2)}</td>
                  <td className={`mono ${net >= 0 ? 'profit' : 'loss'}`}>{net >= 0 ? '+' : ''}{net.toFixed(2)}</td>
                  <td>{d.reason}</td>
                  <td style={{ fontSize: 10, color: 'var(--text-muted)' }}>{d.time?.substring(0, 19)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
