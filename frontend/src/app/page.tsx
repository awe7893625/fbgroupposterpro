'use client'
import { useEffect, useState } from 'react'
import { api } from '../lib/api'

export default function Dashboard() {
  const [health, setHealth] = useState<{status: string; version: string} | null>(null)
  const [report, setReport] = useState<any>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.health().then(setHealth).catch(() => setError('無法連接後端 (localhost:3080)'))
    const today = new Date().toISOString().split('T')[0]
    const from = new Date(Date.now() - 30 * 86400000).toISOString().split('T')[0]
    api.getReport({ from, to: today }).then(setReport).catch(() => {})
  }, [])

  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-800 mb-6">Dashboard</h2>

      {error && <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">{error}</div>}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        {[
          { label: '近30天發文', value: report?.summary?.total ?? '—', color: 'text-blue-600' },
          { label: '成功', value: report?.summary?.success ?? '—', color: 'text-green-600' },
          { label: '失敗', value: report?.summary?.failed ?? '—', color: 'text-red-500' },
          { label: '成功率', value: report?.summary?.success_rate != null ? report.summary.success_rate + '%' : '—', color: 'text-purple-600' },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-200 p-5 text-center shadow-sm">
            <div className={`text-3xl font-bold ${color}`}>{value}</div>
            <div className="text-xs text-gray-500 mt-1">{label}</div>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
        <h3 className="font-semibold text-gray-700 mb-3">系統狀態</h3>
        <div className="flex items-center gap-2">
          <div className={`w-2.5 h-2.5 rounded-full ${health?.status === 'ok' ? 'bg-green-500' : 'bg-red-500'}`}></div>
          <span className="text-sm text-gray-600">
            {health ? `後端運行中 (v${health.version})` : error ? '後端離線' : '連接中...'}
          </span>
        </div>
      </div>
    </div>
  )
}
