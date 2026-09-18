import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getPositions, closePosition } from '../services/api'
import { X } from 'lucide-react'

export default function Positions() {
  const qc = useQueryClient()
  const { data: positions = [] } = useQuery({ queryKey: ['positions'], queryFn: () => getPositions().then(r => r.data) })
  const closeMut = useMutation({ mutationFn: (ticket: number) => closePosition(ticket),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['positions'] }) })

  const totalPnl = positions.reduce((s: number, p: any) => s + Number(p.profit) + Number(p.swap), 0)

  return (
    <div style={{ padding: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h2 style={{ fontSize: 16, fontWeight: 700 }}>Open Positions ({positions.length})</h2>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 14 }}>
          Total P/L: <span className={totalPnl >= 0 ? 'profit' : 'loss'}>
            {totalPnl >= 0 ? '+' : ''}{totalPnl.toFixed(2)}
          </span>
          <span style={{ fontSize: 9, color: 'var(--text-muted)', marginLeft: 6 }}>Provenance: MT5</span>
        </div>
      </div>
      <div className="card" style={{ overflow: 'auto' }}>
        <table>
          <thead><tr>
            <th>Ticket</th><th>Symbol</th><th>Dir</th><th>Vol</th>
            <th>Entry</th><th>Current</th><th>SL</th><th>TP</th>
            <th>P/L</th><th>Swap</th><th>Comment</th><th>Magic</th><th>Action</th>
          </tr></thead>
          <tbody>
            {positions.length === 0 && (
              <tr><td colSpan={13} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 24 }}>No open positions</td></tr>
            )}
            {positions.map((p: any) => {
              const pnl = Number(p.profit)
              return (
                <tr key={p.ticket}>
                  <td className="mono" style={{ color: 'var(--accent)' }}>{p.ticket}</td>
                  <td>{p.symbol}</td>
                  <td><span className={`badge ${p.direction === 'BUY' ? 'badge-green' : 'badge-red'}`}>{p.direction}</span></td>
                  <td className="mono">{p.volume}</td>
                  <td className="mono">{Number(p.price_open).toFixed(2)}</td>
                  <td className="mono">{Number(p.price_current).toFixed(2)}</td>
                  <td className="mono">{Number(p.sl).toFixed(2)}</td>
                  <td className="mono">{Number(p.tp).toFixed(2)}</td>
                  <td className={`mono ${pnl >= 0 ? 'profit' : 'loss'}`}>{pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}</td>
                  <td className="mono">{Number(p.swap).toFixed(2)}</td>
                  <td style={{ maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis' }}>{p.comment}</td>
                  <td className="mono" style={{ color: 'var(--text-muted)' }}>{p.magic}</td>
                  <td>
                    <button className="btn btn-danger btn-sm"
                      onClick={() => { if (confirm(`Close position ${p.ticket}?`)) closeMut.mutate(p.ticket) }}>
                      <X size={10} /> Close
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
