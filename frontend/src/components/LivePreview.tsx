'use client'
import { useEffect, useRef, useState } from 'react'

interface LivePreviewProps {
  accountId?: number
  className?: string
}

export function LivePreview({ accountId, className }: LivePreviewProps) {
  const [screenshot, setScreenshot] = useState<string | null>(null)
  const [status, setStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting')
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    const ws = new WebSocket('ws://localhost:3080/ws')
    wsRef.current = ws

    ws.onopen = () => setStatus('connected')
    ws.onclose = () => setStatus('disconnected')
    ws.onerror = () => setStatus('disconnected')

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'SCREENSHOT') {
          if (!accountId || data.account_id === accountId) {
            setScreenshot(`data:image/png;base64,${data.data}`)
          }
        }
      } catch {}
    }

    return () => { ws.close() }
  }, [accountId])

  return (
    <div className={`bg-gray-900 rounded-xl overflow-hidden ${className}`}>
      <div className="flex items-center justify-between px-3 py-2 bg-gray-800">
        <span className="text-xs text-gray-400">瀏覽器即時預覽</span>
        <div className="flex items-center gap-1.5">
          <div className={`w-2 h-2 rounded-full ${
            status === 'connected' ? 'bg-green-500' :
            status === 'connecting' ? 'bg-yellow-400 animate-pulse' : 'bg-red-500'
          }`}></div>
          <span className="text-xs text-gray-500">{status}</span>
        </div>
      </div>
      {screenshot ? (
        <img src={screenshot} alt="Browser" className="w-full" />
      ) : (
        <div className="flex items-center justify-center h-48 text-gray-500 text-sm">
          {status === 'connected' ? '等待瀏覽器啟動...' : '連接後端中...'}
        </div>
      )}
    </div>
  )
}
