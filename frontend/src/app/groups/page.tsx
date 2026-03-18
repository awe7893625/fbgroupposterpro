'use client'
import { useEffect, useState } from 'react'
import { api, Group, Account } from '../../lib/api'

const PLATFORM_BADGE: Record<string, { label: string; className: string }> = {
  fb:        { label: 'FB',      className: 'bg-blue-100 text-blue-700' },
  threads:   { label: 'Threads', className: 'bg-gray-100 text-gray-700' },
  x:         { label: 'X',       className: 'bg-black text-white' },
  instagram: { label: 'IG',      className: 'bg-pink-100 text-pink-700' },
}

function PlatformBadge({ platform }: { platform?: string }) {
  const p = platform || 'fb'
  const cfg = PLATFORM_BADGE[p] ?? { label: p, className: 'bg-gray-100 text-gray-600' }
  return (
    <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold mr-1.5 ${cfg.className}`}>
      {cfg.label}
    </span>
  )
}

export default function GroupsPage() {
  const [groups, setGroups] = useState<Group[]>([])
  const [accounts, setAccounts] = useState<Account[]>([])
  const [selAccount, setSelAccount] = useState<number | null>(null)
  const [url, setUrl] = useState('')
  const [name, setName] = useState('')
  const [platform, setPlatform] = useState('fb')
  const [msg, setMsg] = useState('')

  useEffect(() => { api.getAccounts().then(setAccounts) }, [])

  const load = (id: number) => api.getGroups(id).then(setGroups)

  const addGroup = async () => {
    if (!selAccount || !url) { setMsg('請選擇帳號並輸入社團 URL'); return }
    try {
      await api.createGroup({ account_id: selAccount, url, name: name || url, platform })
      setUrl('')
      setName('')
      setPlatform('fb')
      setMsg('已加入')
      load(selAccount)
    } catch (e: any) {
      setMsg('錯誤：' + e.message)
    }
  }

  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-800 mb-6">社團管理</h2>
      <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm mb-6">
        <div className="grid grid-cols-5 gap-3">
          <select value={selAccount || ''} onChange={e => { setSelAccount(Number(e.target.value)); load(Number(e.target.value)) }}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm">
            <option value="">選擇帳號</option>
            {accounts.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
          <select value={platform} onChange={e => setPlatform(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm">
            <option value="fb">Facebook 群組</option>
            <option value="threads">Threads</option>
            <option value="x">X（Twitter）⚠️ 高封帳風險</option>
            <option value="instagram">Instagram ⚠️ 極高封帳風險 · 需圖片</option>
          </select>
          <input placeholder="社團 URL" value={url} onChange={e => setUrl(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm" />
          <input placeholder="社團名稱（選填）" value={name} onChange={e => setName(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm" />
          <button onClick={addGroup} className="bg-blue-600 text-white rounded-lg px-4 py-2 text-sm hover:bg-blue-700">新增</button>
        </div>
        {msg && <p className="mt-2 text-sm text-gray-600">{msg}</p>}
      </div>
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-600">
            <tr>
              {['社團名稱', 'URL', '標籤', '發文次數', '操作'].map(h => (
                <th key={h} className="px-4 py-3 text-left">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {groups.map(g => (
              <tr key={g.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-medium">
                  <PlatformBadge platform={g.platform} />
                  {g.name}
                </td>
                <td className="px-4 py-3 text-gray-400 text-xs truncate max-w-[200px]">{g.url}</td>
                <td className="px-4 py-3 text-gray-500 text-xs">{g.tag || '—'}</td>
                <td className="px-4 py-3">{g.post_count}</td>
                <td className="px-4 py-3">
                  <button onClick={() => { api.deleteGroup(g.id).then(() => { if (selAccount) load(selAccount) }) }}
                    className="text-red-500 text-xs hover:underline">刪除</button>
                </td>
              </tr>
            ))}
            {groups.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400">尚無社團，請選擇帳號後新增</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
