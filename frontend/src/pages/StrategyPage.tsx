import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getStrategy, updateStrategy, getExposurePreview } from '../services/api'
import { useState, useEffect } from 'react'
import { AlertTriangle } from 'lucide-react'

export default function StrategyPage() {
  const qc = useQueryClient()
  const { data: strat } = useQuery({ queryKey: ['strategy'], queryFn: () => getStrategy().then(r => r.data) })
  const { data: exposure } = useQuery({ queryKey: ['exposure'], queryFn: () => getExposurePreview().then(r => r.data) })
  const mut = useMutation({ mutationFn: updateStrategy, onSuccess: () => qc.invalidateQueries({ queryKey: ['strategy', 'exposure'] }) })

  const [cfg, setCfg] = useState<any>(null)
  useEffect(() => { if (strat) setCfg(strat) }, [strat])

  if (!cfg) return <div style={{ padding: 20, color: 'var(--text-muted)' }}>Loading strategy...</div>

  const set = (k: string, v: any) => setCfg((c: any) => ({ ...c, [k]: v }))

  return (
    <div style={{ padding: 12, display: 'flex', gap: 12 }}>
      {/* Config form */}
      <div style={{ flex: 1 }}>
        <div className="card">
          <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span><AlertTriangle size={12} /> Grid Strategy Config</span>
            <div style={{ display: 'flex', gap: 6 }}>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                style={{ fontSize: 10, borderColor: 'var(--green)', color: 'var(--green)' }}
                onClick={() => setCfg({
                  ...cfg,
                  strategy_id: 'xauusd_fast_grid',
                  symbol: 'XAUUSD',
                  direction: cfg.direction || 'BUY',
                  grid_mode: 'adverse',
                  grid_anchor: 'last_entry',
                  first_entry: 'immediate_on_start',
                  initial_lot: 0.01,
                  lot_mode: 'fixed',
                  lot_multiplier: 1.0,
                  allow_multiplier: false,
                  max_lot: 0.05,
                  max_total_lots: 0.50,
                  max_positions: 40,
                  grid_distance_points: 40,
                  basket_take_profit: 3.0,
                  basket_stop_loss: 50.0,
                  cooldown_seconds: 0,
                  rearm_after_basket_close: true,
                  rearm_delay_seconds: 5,
                  aggressive_mode: true,
                })}
              >
                ⚡ Load Fast Scalp Grid (Video-Style)
              </button>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                style={{ fontSize: 10 }}
                onClick={() => setCfg({
                  ...cfg,
                  strategy_id: 'xauusd_conservative',
                  symbol: 'XAUUSD',
                  direction: cfg.direction || 'BUY',
                  grid_mode: 'adverse',
                  grid_anchor: 'last_entry',
                  first_entry: 'manual_trigger',
                  initial_lot: 0.01,
                  lot_mode: 'fixed',
                  lot_multiplier: 1.0,
                  allow_multiplier: false,
                  max_lot: 0.05,
                  max_total_lots: 0.20,
                  max_positions: 10,
                  grid_distance_points: 100,
                  basket_take_profit: 10.0,
                  basket_stop_loss: 30.0,
                  cooldown_seconds: 30,
                  rearm_after_basket_close: false,
                  aggressive_mode: false,
                })}
              >
                🛡 Conservative
              </button>
            </div>
          </div>
          <div className="card-body" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>

            {/* --- Section: Identity --- */}
            <div style={{ gridColumn: '1/-1' }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '.5px' }}>Identity</div>
            </div>
            <div><label>Strategy ID</label><input value={cfg.strategy_id} onChange={e => set('strategy_id', e.target.value)} /></div>
            <div><label>Symbol</label><input value={cfg.symbol} onChange={e => set('symbol', e.target.value)} /></div>

            {/* --- Section: Grid --- */}
            <div style={{ gridColumn: '1/-1', marginTop: 8 }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '.5px' }}>Grid Settings</div>
            </div>
            <div>
              <label>Direction</label>
              <select value={cfg.direction} onChange={e => set('direction', e.target.value)}>
                <option>SELL</option><option>BUY</option>
              </select>
            </div>
            <div>
              <label>Grid Mode</label>
              <select value={cfg.grid_mode} onChange={e => set('grid_mode', e.target.value)}>
                <option value="adverse">Adverse (add against position)</option>
                <option value="favorable">Favorable</option>
              </select>
            </div>
            <div>
              <label>Grid Anchor</label>
              <select value={cfg.grid_anchor} onChange={e => set('grid_anchor', e.target.value)}>
                <option value="last_entry">Last Entry</option>
                <option value="average_entry">Average Entry</option>
              </select>
            </div>
            <div>
              <label>First Entry</label>
              <select value={cfg.first_entry} onChange={e => set('first_entry', e.target.value)}>
                <option value="manual_trigger">Manual Trigger</option>
                <option value="immediate_on_start">Immediate on Start</option>
              </select>
            </div>
            <div>
              <label>Grid Distance (points)</label>
              <input type="number" value={cfg.grid_distance_points} onChange={e => set('grid_distance_points', +e.target.value)} />
            </div>
            <div>
              <label>Max Positions</label>
              <input type="number" value={cfg.max_positions} onChange={e => set('max_positions', +e.target.value)} />
            </div>
            <div>
              <label>Cooldown (seconds)</label>
              <input type="number" value={cfg.cooldown_seconds} onChange={e => set('cooldown_seconds', +e.target.value)} />
            </div>

            {/* --- Section: Sizing --- */}
            <div style={{ gridColumn: '1/-1', marginTop: 8 }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '.5px' }}>Position Sizing</div>
            </div>
            <div>
              <label>Initial Lot</label>
              <input type="number" step="0.01" value={cfg.initial_lot} onChange={e => set('initial_lot', +e.target.value)} />
            </div>
            <div>
              <label>Lot Mode</label>
              <select value={cfg.lot_mode} onChange={e => set('lot_mode', e.target.value)}>
                <option value="fixed">Fixed</option>
                <option value="multiplier">Multiplier</option>
                <option value="custom">Custom</option>
              </select>
            </div>
            {cfg.lot_mode === 'multiplier' && (
              <>
                <div>
                  <label>Lot Multiplier</label>
                  <input type="number" step="0.1" value={cfg.lot_multiplier} onChange={e => set('lot_multiplier', +e.target.value)} />
                  {cfg.lot_multiplier > 1.0 && (
                    <div className="alert alert-warning" style={{ marginTop: 4, fontSize: 10 }}>
                      ⚠ Multiplier &gt; 1.0 is MARTINGALE. Enable allow_multiplier to proceed.
                    </div>
                  )}
                </div>
                <div>
                  <label>Allow Multiplier (required for multiplier &gt; 1.0)</label>
                  <select value={cfg.allow_multiplier ? 'true' : 'false'} onChange={e => set('allow_multiplier', e.target.value === 'true')}>
                    <option value="false">No</option>
                    <option value="true">Yes (I understand the risks)</option>
                  </select>
                </div>
              </>
            )}
            <div>
              <label>Max Lot (per position)</label>
              <input type="number" step="0.01" value={cfg.max_lot} onChange={e => set('max_lot', +e.target.value)} />
            </div>
            <div>
              <label>Max Total Lots</label>
              <input type="number" step="0.01" value={cfg.max_total_lots} onChange={e => set('max_total_lots', +e.target.value)} />
            </div>

            {/* --- Section: TP/SL --- */}
            <div style={{ gridColumn: '1/-1', marginTop: 8 }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '.5px' }}>Basket TP / SL</div>
            </div>
            <div>
              <label>Basket Take Profit ({cfg.symbol} currency)</label>
              <input type="number" value={cfg.basket_take_profit} onChange={e => set('basket_take_profit', +e.target.value)} />
            </div>
            <div>
              <label>Basket Stop Loss (positive = max loss)</label>
              <input type="number" value={cfg.basket_stop_loss} onChange={e => set('basket_stop_loss', +e.target.value)} />
            </div>
            <div>
              <label>P/L Basis</label>
              <select value={cfg.basket_pnl_basis} onChange={e => set('basket_pnl_basis', e.target.value)}>
                <option value="net">Net (includes commission)</option>
                <option value="gross">Gross (excluding commission)</option>
              </select>
            </div>
            <div>
              <label>Protective SL (points)</label>
              <input type="number" value={cfg.protective_sl_points} onChange={e => set('protective_sl_points', +e.target.value)} />
            </div>

            {/* --- Section: Execution --- */}
            <div style={{ gridColumn: '1/-1', marginTop: 8 }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '.5px' }}>Execution</div>
            </div>
            <div>
              <label>Max Slippage (points)</label>
              <input type="number" value={cfg.max_slippage_points} onChange={e => set('max_slippage_points', +e.target.value)} />
            </div>
            <div>
              <label>Max Spread (points)</label>
              <input type="number" value={cfg.max_spread_points} onChange={e => set('max_spread_points', +e.target.value)} />
            </div>
            <div>
              <label>Max Entries / Hour</label>
              <input type="number" value={cfg.max_entries_per_hour} onChange={e => set('max_entries_per_hour', +e.target.value)} />
            </div>
            <div>
              <label>Rearm After Basket Close</label>
              <select value={cfg.rearm_after_basket_close ? 'true' : 'false'}
                onChange={e => set('rearm_after_basket_close', e.target.value === 'true')}>
                <option value="false">No (disarm after basket)</option>
                <option value="true">Yes (auto rearm)</option>
              </select>
            </div>

            <div style={{ gridColumn: '1/-1', marginTop: 8 }}>
              <button className="btn btn-primary" onClick={() => mut.mutate(cfg)}
                disabled={mut.isPending} style={{ width: '100%' }}>
                {mut.isPending ? 'Saving...' : 'Save Configuration'}
              </button>
              {mut.isError && <div className="alert alert-error" style={{ marginTop: 8 }}>
                Save failed: {(mut.error as any)?.response?.data?.detail || 'Unknown error'}
              </div>}
              {mut.isSuccess && <div className="alert alert-success" style={{ marginTop: 8 }}>Saved!</div>}
            </div>
          </div>
        </div>
      </div>

      {/* Exposure preview */}
      {exposure && (
        <div style={{ width: 260 }}>
          <div className="card">
            <div className="card-header">Worst-Case Exposure</div>
            <div className="card-body" style={{ fontSize: 11 }}>
              <div style={{ marginBottom: 8 }}>
                <div className="stat-label">Max Positions</div>
                <div className="mono">{exposure.max_positions}</div>
              </div>
              <div style={{ marginBottom: 8 }}>
                <div className="stat-label">Total Lots (worst-case)</div>
                <div className="mono">{exposure.total_lots}</div>
              </div>
              <div style={{ marginBottom: 8 }}>
                <div className="stat-label">Basket SL</div>
                <div className="mono loss">{exposure.basket_sl}</div>
              </div>
              <div style={{ marginBottom: 10 }}>
                <div className="stat-label">Lots Per Level</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 4 }}>
                  {exposure.lots_per_level?.map((l: string, i: number) => (
                    <span key={i} className="badge badge-muted">{i}: {l}</span>
                  ))}
                </div>
              </div>
              <div className="alert alert-warning" style={{ fontSize: 10 }}>
                {exposure.warning}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
