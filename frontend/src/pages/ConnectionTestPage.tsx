import { useMutation } from '@tanstack/react-query'
import { runConnectionTest, getLatestTest } from '../services/api'
import { useQuery } from '@tanstack/react-query'
import { CheckCircle, XCircle, FlaskConical } from 'lucide-react'
import { useState } from 'react'

export default function ConnectionTestPage() {
  const [confirmed, setConfirmed] = useState(false)
  const { data: latest, refetch } = useQuery({
    queryKey: ['conntest'],
    queryFn: () => getLatestTest().then(r => r.data),
    refetchInterval: false,
  })

  const mut = useMutation({
    mutationFn: runConnectionTest,
    onSuccess: () => refetch(),
  })

  const result = mut.data?.data || (latest?.found ? latest : null)

  return (
    <div style={{ padding: 12, maxWidth: 700 }}>
      <div className="card">
        <div className="card-header"><FlaskConical size={12} /> MT5 Connection Test</div>
        <div className="card-body">
          <div className="alert alert-info" style={{ marginBottom: 12 }}>
            This test places a 0.01 lot demo trade and immediately closes it to verify full round-trip connectivity.
            A cleanup guarantee ensures the test position is always closed.
          </div>

          {!confirmed ? (
            <div>
              <div className="alert alert-warning" style={{ marginBottom: 12 }}>
                ⚠ This will place a REAL 0.01 lot order on your DEMO account and close it immediately.
                Only proceed if you understand and accept this.
              </div>
              <button className="btn btn-primary" onClick={() => setConfirmed(true)}>
                I Understand — Proceed to Test
              </button>
            </div>
          ) : (
            <button className="btn btn-primary" onClick={() => mut.mutate()}
              disabled={mut.isPending}>
              {mut.isPending ? 'Running Test...' : 'Run Connection Test'}
            </button>
          )}

          {result && result.stages && (
            <div style={{ marginTop: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                {result.overall_passed
                  ? <CheckCircle size={20} color="var(--green)" />
                  : <XCircle size={20} color="var(--red)" />}
                <span style={{ fontWeight: 700, fontSize: 14,
                  color: result.overall_passed ? 'var(--green)' : 'var(--red)' }}>
                  {result.overall_passed ? 'ALL STAGES PASSED' : 'SOME STAGES FAILED'}
                </span>
                {result.tested_at && (
                  <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                    {result.tested_at?.substring(0, 19)}
                  </span>
                )}
              </div>
              <table>
                <thead><tr><th>#</th><th>Stage</th><th>Result</th><th>Detail</th><th>Latency</th></tr></thead>
                <tbody>
                  {result.stages.map((s: any, i: number) => (
                    <tr key={i}>
                      <td className="mono" style={{ color: 'var(--text-muted)' }}>{i + 1}</td>
                      <td className="mono" style={{ fontSize: 11 }}>{s.stage}</td>
                      <td>
                        {s.passed
                          ? <span className="badge badge-green">PASS</span>
                          : <span className="badge badge-red">FAIL</span>}
                      </td>
                      <td style={{ fontSize: 11, color: 'var(--text-secondary)', maxWidth: 300,
                        overflow: 'hidden', textOverflow: 'ellipsis' }}>{s.detail}</td>
                      <td className="mono" style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                        {s.latency_ms > 0 ? `${s.latency_ms}ms` : ''}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
