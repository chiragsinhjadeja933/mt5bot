import { useQuery } from '@tanstack/react-query'
import { getLogs } from '../services/api'
import { useState } from 'react'

const LEVELS = ['', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

export default function LogsPage() {
  const [level, setLevel] = useState('')
  const { data: logs = [] } = useQuery({
    queryKey: ['logs', level],
    queryFn: () => getLogs({ level: level || undefined, limit: 500 }).then(r => r.data),
    refetchInterval: 3000,
  })

  return (
    <div style={{ padding: 12 }}>
      <div style={{ display: 'flex', gap: 10, marginBottom: 12, alignItems: 'flex-end' }}>
        <div>
          <label>Level</label>
          <select value={level} onChange={e => setLevel(e.target.value)} style={{ width: 120 }}>
            {LEVELS.map(l => <option key={l} value={l}>{l || 'ALL'}</option>)}
          </select>
        </div>
        <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>{logs.length} entries</span>
      </div>
      <div className="card" style={{ overflow: 'auto', maxHeight: 'calc(100vh - 160px)' }}>
        <table>
          <thead><tr>
            <th>Time</th><th>Level</th><th>Component</th><th>Message</th>
          </tr></thead>
          <tbody>
            {logs.length === 0 && (
              <tr><td colSpan={4} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 24 }}>No logs</td></tr>
            )}
            {logs.map((l: any) => (
              <tr key={l.id}>
                <td style={{ fontSize: 10, color: 'var(--text-muted)', width: 160 }}>
                  {l.created_at?.substring(0, 19)}
                </td>
                <td>
                  <span className={`badge ${
                    l.severity === 'ERROR' || l.severity === 'CRITICAL' ? 'badge-red' :
                    l.severity === 'WARNING' ? 'badge-yellow' : 'badge-muted'
                  }`}>{l.severity}</span>
                </td>
                <td style={{ fontSize: 11, color: 'var(--text-secondary)', width: 140 }}>{l.component}</td>
                <td style={{ fontSize: 11, fontFamily: 'var(--font-mono)', wordBreak: 'break-all' }}>{l.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
