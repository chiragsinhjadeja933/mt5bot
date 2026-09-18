import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getRisk, updateRisk } from '../services/api'
import { useState, useEffect } from 'react'
import { Shield } from 'lucide-react'

export default function RiskPage() {
  const qc = useQueryClient()
  const { data: risk } = useQuery({ queryKey: ['risk'], queryFn: () => getRisk().then(r => r.data) })
  const mut = useMutation({ mutationFn: updateRisk, onSuccess: () => qc.invalidateQueries({ queryKey: ['risk'] }) })
  const [cfg, setCfg] = useState<any>(null)
  useEffect(() => { if (risk) setCfg(risk) }, [risk])
  if (!cfg) return null

  const set = (k: string, v: any) => setCfg((c: any) => ({ ...c, [k]: v }))

  const fields: [string, string, string][] = [
    ['max_daily_loss_pct', 'Max Daily Loss %', '%'],
    ['max_drawdown_pct', 'Max Drawdown %', '%'],
    ['max_open_positions', 'Max Open Positions', ''],
    ['max_total_volume', 'Max Total Volume', 'lots'],
    ['max_margin_usage_pct', 'Max Margin Usage %', '%'],
    ['min_margin_level_pct', 'Min Margin Level %', '%'],
    ['max_spread_points', 'Max Spread', 'pts'],
    ['max_consecutive_losses', 'Max Consecutive Losses', ''],
    ['max_basket_loss', 'Max Basket Loss', 'ccy'],
    ['max_entries_per_hour', 'Max Entries/Hour', ''],
  ]

  return (
    <div style={{ padding: 12 }}>
      <div className="card" style={{ maxWidth: 600 }}>
        <div className="card-header"><Shield size={12} /> Risk Limits</div>
        <div className="card-body">
          <div className="alert alert-info" style={{ marginBottom: 12 }}>
            These are hard limits independent of strategy. Latching limits require manual reset.
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            {fields.map(([key, label, unit]) => (
              <div key={key}>
                <label>{label} {unit && <span style={{ color: 'var(--text-muted)' }}>({unit})</span>}</label>
                <input type="number" step="0.1" value={cfg[key]}
                  onChange={e => set(key, +e.target.value)} />
              </div>
            ))}
            <div>
              <label>Close on Emergency</label>
              <select value={cfg.close_on_emergency ? 'true' : 'false'}
                onChange={e => set('close_on_emergency', e.target.value === 'true')}>
                <option value="true">Yes</option><option value="false">No</option>
              </select>
            </div>
          </div>
          <div style={{ marginTop: 16 }}>
            <button className="btn btn-primary" onClick={() => mut.mutate(cfg)}
              disabled={mut.isPending} style={{ width: '100%' }}>
              {mut.isPending ? 'Saving...' : 'Save Risk Config'}
            </button>
            {mut.isSuccess && <div className="alert alert-success" style={{ marginTop: 8 }}>Saved!</div>}
          </div>
        </div>
      </div>
    </div>
  )
}
