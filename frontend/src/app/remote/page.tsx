'use client'
import { useCallback, useEffect, useState } from 'react'
import { QRCodeSVG } from 'qrcode.react'

interface RemoteStatus {
  enabled: boolean
  token: string
  tailscale_ip: string
  port: number
}

function getBase(): string {
  if (typeof window === 'undefined') return 'http://localhost:3080'
  return localStorage?.getItem('remote_api_base') || window.location.origin
}

export default function RemotePage() {
  const [status, setStatus] = useState<RemoteStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [actionLoading, setActionLoading] = useState(false)

  const fetchStatus = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await fetch(`${getBase()}/api/remote/status`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: RemoteStatus = await res.json()
      setStatus(data)
    } catch (e: any) {
      setError('無法取得遠端狀態：' + e.message)
      setStatus(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchStatus() }, [fetchStatus])

  const toggleRemote = async (enable: boolean) => {
    setActionLoading(true)
    setError('')
    try {
      const endpoint = enable ? 'enable' : 'disable'
      const res = await fetch(`${getBase()}/api/remote/${endpoint}`, { method: 'POST' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      await fetchStatus()
    } catch (e: any) {
      setError(enable ? '啟用失敗：' + e.message : '停用失敗：' + e.message)
    } finally {
      setActionLoading(false)
    }
  }

  const regenerateToken = async () => {
    setActionLoading(true)
    setError('')
    try {
      const res = await fetch(`${getBase()}/api/remote/regenerate-token`, { method: 'POST' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      await fetchStatus()
    } catch (e: any) {
      setError('重新產生 Token 失敗：' + e.message)
    } finally {
      setActionLoading(false)
    }
  }

  // http (the PC engine serves plain HTTP on the tailnet — no TLS on this port)
  const remoteUrl = status?.enabled && status.tailscale_ip
    ? `http://${status.tailscale_ip}:${status.port}/?token=${status.token}`
    : ''

  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-800 mb-6">遠端存取</h2>

      {error && (
        <div className="mb-4 bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700 shadow-sm">
          {error}
        </div>
      )}

      {loading ? (
        <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-500 shadow-sm">
          載入中...
        </div>
      ) : (
        <>
          <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm mb-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="font-semibold text-gray-700">遠端狀態</h3>
                <p className="text-xs text-gray-500 mt-1">
                  {status?.enabled
                    ? '遠端存取已啟用，可透過 Tailscale 連線'
                    : '遠端存取目前停用'}
                </p>
              </div>
              <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                status?.enabled ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
              }`}>
                {status?.enabled ? '● 啟用' : '○ 停用'}
              </span>
            </div>

            <div className="flex gap-2">
              {status?.enabled ? (
                <button onClick={() => toggleRemote(false)} disabled={actionLoading}
                  className="bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors">
                  {actionLoading ? '處理中...' : '停用遠端'}
                </button>
              ) : (
                <button onClick={() => toggleRemote(true)} disabled={actionLoading}
                  className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors">
                  {actionLoading ? '處理中...' : '啟用遠端'}
                </button>
              )}
              {status?.enabled && (
                <button onClick={regenerateToken} disabled={actionLoading}
                  className="border border-gray-300 hover:bg-gray-50 disabled:opacity-50 text-gray-700 rounded-lg px-4 py-2 text-sm font-medium transition-colors">
                  {actionLoading ? '處理中...' : '重新產生 Token'}
                </button>
              )}
            </div>
          </div>

          {status?.enabled && (
            <>
              <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm mb-6">
                <h3 className="font-semibold text-gray-700 mb-3">存取 Token</h3>
                <div className="flex items-center gap-2">
                  <code className="flex-1 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-800 font-mono break-all">
                    {status.token}
                  </code>
                  <button
                    onClick={() => navigator.clipboard?.writeText(status.token)}
                    className="text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 rounded px-3 py-2 font-medium transition-colors"
                  >
                    複製
                  </button>
                </div>
                <p className="text-xs text-gray-500 mt-2">
                  請妥善保管此 Token，重新產生後舊 Token 將立即失效。
                </p>
              </div>

              {status.tailscale_ip && remoteUrl && (
                <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm mb-6">
                  <h3 className="font-semibold text-gray-700 mb-3">QR Code</h3>
                  <div className="flex flex-col items-center">
                    {/* QR generated locally (qrcode.react) — the token never leaves this PC */}
                    <div className="border border-gray-200 rounded-lg p-3 bg-white">
                      <QRCodeSVG value={remoteUrl} size={232} level="M" />
                    </div>
                    <p className="text-xs text-gray-500 mt-3">
                      手機掃描即可自動連線（已含 Token，請勿外流此 QR）
                    </p>
                  </div>
                </div>
              )}
              {!status.tailscale_ip && (
                <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-800 mb-6">
                  偵測不到 Tailscale IP。請先在這台電腦安裝並登入 Tailscale，再回此頁產生手機連線 QR。
                </div>
              )}

              {remoteUrl && (
                <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm mb-6">
                  <h3 className="font-semibold text-gray-700 mb-3">Remote URL</h3>
                  <div className="flex items-center gap-2">
                    <code className="flex-1 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-800 font-mono break-all">
                      {remoteUrl}
                    </code>
                    <button
                      onClick={() => navigator.clipboard?.writeText(remoteUrl)}
                      className="text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 rounded px-3 py-2 font-medium transition-colors"
                    >
                      複製
                    </button>
                  </div>
                  {status.tailscale_ip && (
                    <p className="text-xs text-gray-500 mt-2">
                      Tailscale IP: <span className="font-mono">{status.tailscale_ip}</span> · Port: <span className="font-mono">{status.port}</span>
                    </p>
                  )}
                </div>
              )}
            </>
          )}

          {!status?.enabled && !error && (
            <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-400 shadow-sm">
              遠端存取未啟用。點擊「啟用遠端」以透過 Tailscale 從其他裝置存取本服務。
            </div>
          )}
        </>
      )}
    </div>
  )
}
