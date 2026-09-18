import { useEffect, useRef } from 'react'
import { useStore } from '../store/useStore'

const WS_URL = import.meta.env.VITE_WS_URL || `ws://127.0.0.1:8000/ws?token=${import.meta.env.VITE_API_TOKEN || 'dev'}`
const RECONNECT_MS = [1000, 2000, 4000, 8000, 15000]

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null)
  const retryRef = useRef(0)
  const mountedRef = useRef(true)
  const { setWsStatus, setSystemState, setAccount, setTick, setPositions, setBasket, addAlert } = useStore()

  useEffect(() => {
    mountedRef.current = true

    function connect() {
      if (!mountedRef.current) return
      setWsStatus('connecting')
      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => {
        retryRef.current = 0
        setWsStatus('live')
      }

      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data)
          if (msg.state) setSystemState(msg.state)
          if (msg.account) setAccount(msg.account)
          if (msg.tick) setTick(msg.tick)
          if (msg.positions) setPositions(msg.positions)
          if (msg.basket) setBasket(msg.basket)
          if (msg.type === 'alert') addAlert(msg.message, msg.level)
        } catch { /* ignore */ }
      }

      ws.onclose = () => {
        if (!mountedRef.current) return
        setWsStatus('reconnecting')
        const delay = RECONNECT_MS[Math.min(retryRef.current, RECONNECT_MS.length - 1)]
        retryRef.current++
        setTimeout(connect, delay)
      }

      ws.onerror = () => {
        ws.close()
      }

      // Heartbeat ping every 25s
      const ping = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send('ping')
      }, 25000)
      ws.addEventListener('close', () => clearInterval(ping))
    }

    connect()
    return () => {
      mountedRef.current = false
      wsRef.current?.close()
    }
  }, [])
}
