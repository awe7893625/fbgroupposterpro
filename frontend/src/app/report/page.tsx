'use client'
import { useEffect, useState } from 'react'
import { api, ReportResponse } from '../../lib/api'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

export default function ReportPage() {
  const [report, setReport] = useState<ReportResponse | null>(null)
  const [from, setFrom] = useState(new Date(Date.now() - 30 * 86400000).toISOString().split('T')[0])
  const [to, setTo] = useState(new Date().toISOString().split('T')[0])

  const load = () => api.getReport({ from, to }).then(setReport).catch(console.error)
  useEffect(() => { load() }, [])

  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-800 mb-6">發文報表</h2>
      <div className="flex gap-3 mb-6 items-end">
        <div>
          <label className="text-xs text-gray-500 block mb-1">開始日期</label>
          <input type="date" value={from} onChange={e => setFrom(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm" />
        </div>
        <div>
          <label className="text-xs text-gray-500 block mb-1">結束日期</label>
          <input type="date" value={to} onChange={e => setTo(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm" />
        </div>
        <button onClick={load} className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700">載入</button>
      </div>

      {report && <>
        <div className="grid grid-cols-4 gap-4 mb-6">
          {[
            { label: '總發文', value: report.summary.total, color: 'text-blue-600' },
            { label: '成功', value: report.summary.success, color: 'text-green-600' },
            { label: '失敗', value: report.summary.failed, color: 'text-red-500' },
            { label: '成功率', value: report.summary.success_rate + '%', color: 'text-purple-600' },
          ].map(({ label, value, color }) => (
            <div key={label} className="bg-white rounded-xl border border-gray-200 p-4 text-center shadow-sm">
              <div className={`text-2xl font-bold ${color}`}>{value}</div>
              <div className="text-xs text-gray-500 mt-1">{label}</div>
            </div>
          ))}
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm mb-6">
          <h3 className="font-semibold text-gray-700 mb-4">每日發文趨勢</h3>
          <div style={{height: 200}}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={buildChartData(report.records)}>
                <XAxis dataKey="date" tick={{fontSize: 11}} />
                <YAxis tick={{fontSize: 11}} />
                <Tooltip />
                <Bar dataKey="count" fill="#3b82f6" radius={[4,4,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div style={{overflowX: 'auto'}}>
            <table className="w-full text-sm min-w-[600px]">
              <thead className="bg-gray-50 text-gray-600">
                <tr>
                  {['社團名稱', '狀態', '發文時間', '連結'].map(h => (
                    <th key={h} className="px-4 py-3 text-left">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {report.records.map(r => (
                  <tr key={r.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 max-w-[200px] truncate" title={r.group_name}>{r.group_name}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                        r.status === 'active' ? 'bg-green-100 text-green-700' :
                        r.status === 'failed' ? 'bg-red-100 text-red-600' :
                        r.status === 'deleted' ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-600'
                      }`}>{r.status}</span>
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs whitespace-nowrap">
                      {r.posted_at ? new Date(r.posted_at).toLocaleString('zh-TW') : '—'}
                    </td>
                    <td className="px-4 py-3">
                      {r.fb_post_url
                        ? <a href={r.fb_post_url} target="_blank" className="text-blue-600 hover:underline text-xs">查看</a>
                        : '—'}
                    </td>
                  </tr>
                ))}
                {report.records.length === 0 && (
                  <tr><td colSpan={4} className="px-4 py-8 text-center text-gray-400">此期間無記錄</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </>}
    </div>
  )
}

function buildChartData(records: any[]) {
  const counts: Record<string, number> = {}
  records.forEach(r => {
    if (r.posted_at) {
      const date = r.posted_at.split('T')[0]
      counts[date] = (counts[date] || 0) + 1
    }
  })
  return Object.entries(counts).sort().slice(-14).map(([date, count]) => ({ date: date.slice(5), count }))
}
