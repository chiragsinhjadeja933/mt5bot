import { create } from 'zustand'

export interface AccountState {
  login?: number; server?: string; currency?: string; trade_mode_name?: string;
  balance?: string; equity?: string; free_margin?: string; margin_level?: string;
  profit?: string; leverage?: number; margin_mode_name?: string;
}

export interface TickState {
  bid?: string; ask?: string; spread_points?: number; age_ms?: number;
  display_price?: string; is_stale?: boolean; is_frozen?: boolean;
}

export interface SystemState {
  connection_state: string; bot_state: string; execution_mode: string;
  display_state: string; emergency_stop_persisted?: boolean;
  sequence_number?: number; error_reason?: string;
}

export interface Position {
  ticket: number; symbol: string; direction: string; volume: string;
  price_open: string; price_current: string; sl: string; tp: string;
  profit: string; swap: string; magic: number; comment: string;
}

interface AppStore {
  connected: boolean
  wsStatus: 'connecting' | 'live' | 'reconnecting' | 'stale'
  systemState: SystemState
  account: AccountState | null
  tick: TickState | null
  positions: Position[]
  alerts: { id: number; msg: string; level: string }[]
  setConnected: (v: boolean) => void
  setWsStatus: (s: AppStore['wsStatus']) => void
  setSystemState: (s: SystemState) => void
  setAccount: (a: AccountState) => void
  setTick: (t: TickState) => void
  setPositions: (p: Position[]) => void
  addAlert: (msg: string, level?: string) => void
  dismissAlert: (id: number) => void
}

let alertId = 0

export const useStore = create<AppStore>((set) => ({
  connected: false,
  wsStatus: 'connecting',
  systemState: { connection_state: 'DISCONNECTED', bot_state: 'READY',
                  execution_mode: 'DRY_RUN', display_state: 'DISCONNECTED' },
  account: null,
  tick: null,
  positions: [],
  alerts: [],

  setConnected: (v) => set({ connected: v }),
  setWsStatus: (s) => set({ wsStatus: s }),
  setSystemState: (s) => set({ systemState: s }),
  setAccount: (a) => set({ account: a }),
  setTick: (t) => set({ tick: t }),
  setPositions: (p) => set({ positions: p }),
  addAlert: (msg, level = 'info') =>
    set((s) => ({ alerts: [...s.alerts, { id: ++alertId, msg, level }].slice(-20) })),
  dismissAlert: (id) =>
    set((s) => ({ alerts: s.alerts.filter((a) => a.id !== id) })),
}))
