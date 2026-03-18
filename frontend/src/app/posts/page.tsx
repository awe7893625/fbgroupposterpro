'use client'
import { useEffect, useState } from 'react'
import { api, Post, Group, Account } from '../../lib/api'
import { LivePreview } from '../../components/LivePreview'

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
    <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold ${cfg.className}`}>
      {cfg.label}
    </span>
  )
}

export default function PostsPage() {
  const [posts, setPosts] = useState<Post[]>([])
  const [accounts, setAccounts] = useState<Account[]>([])
  const [groups, setGroups] = useState<Group[]>([])
  const [selAccount, setSelAccount] = useState<number | null>(null)
  const [form, setForm] = useState({ content: '', interval_seconds: 90, auto_delete_days: 0 })
  const [selGroups, setSelGroups] = useState<number[]>([])
  const [loading, setLoading] = useState(false)
  const [msg, setMsg] = useState('')

  useEffect(() => {
    api.getPosts().then(setPosts)
    api.getAccounts().then(setAccounts)
  }, [])

  useEffect(() => {
    if (selAccount) api.getGroups(selAccount).then(setGroups)
  }, [selAccount])

  const submitPost = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selAccount || selGroups.length === 0) { setMsg('請選擇帳號和至少一個社團'); return }
    setLoading(true)
    try {
      const result = await api.createPost({
        account_id: selAccount,
        content: form.content,
        group_ids: selGroups,
        interval_seconds: form.interval_seconds,
        auto_delete_days: form.auto_delete_days || undefined,
      })
      setMsg(`發文任務建立成功 (ID: ${result.post_id})`)
      api.getPosts().then(setPosts)
    } catch (e: any) {
      setMsg('錯誤：' + e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-800 mb-6">發文佇列</h2>
      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2 space-y-4">
          <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
            <h3 className="font-semibold text-gray-700 mb-4">建立發文任務</h3>
            <form onSubmit={submitPost} className="space-y-3">
              <select required value={selAccount || ''} onChange={e => setSelAccount(Number(e.target.value))}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm">
                <option value="">選擇帳號</option>
                {accounts.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
              </select>
              <textarea required placeholder="發文內容..." rows={5} value={form.content}
                onChange={e => setForm(f => ({...f, content: e.target.value}))}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm resize-none" />
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-gray-500 block mb-1">發文間隔（秒）</label>
                  <input type="number" min={30} value={form.interval_seconds}
                    onChange={e => setForm(f => ({...f, interval_seconds: Number(e.target.value)}))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm" />
                </div>
                <div>
                  <label className="text-xs text-gray-500 block mb-1">N天後自動刪文（0=不刪）</label>
                  <input type="number" min={0} value={form.auto_delete_days}
                    onChange={e => setForm(f => ({...f, auto_delete_days: Number(e.target.value)}))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm" />
                </div>
              </div>
              <div>
                <label className="text-xs text-gray-500 block mb-2">目標社團（{selGroups.length} 個已選）</label>
                <div className="max-h-40 overflow-y-auto border border-gray-200 rounded-lg p-2 space-y-1">
                  {groups.length === 0 && (
                    <p className="text-xs text-gray-400 p-2">請先選擇帳號並在社團管理中加入社團</p>
                  )}
                  {groups.map(g => (
                    <label key={g.id} className="flex items-center gap-2 px-2 py-1 hover:bg-gray-50 rounded cursor-pointer">
                      <input type="checkbox" checked={selGroups.includes(g.id)}
                        onChange={e => setSelGroups(s => e.target.checked ? [...s, g.id] : s.filter(x => x !== g.id))} />
                      <PlatformBadge platform={g.platform} />
                      <span className="text-xs text-gray-700">{g.name}</span>
                      {g.platform === 'instagram' && (
                        <span className="text-orange-500 text-[10px] ml-1">需圖片</span>
                      )}
                    </label>
                  ))}
                </div>
              </div>
              <button type="submit" disabled={loading}
                className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg px-4 py-2 text-sm font-medium">
                {loading ? '建立中...' : '加入發文佇列'}
              </button>
              {msg && <p className="text-sm text-gray-600">{msg}</p>}
            </form>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-100 flex justify-between items-center">
              <h3 className="font-semibold text-gray-700">發文任務列表</h3>
              <button onClick={() => api.getPosts().then(setPosts)} className="text-xs text-blue-600 hover:underline">重新整理</button>
            </div>
            <div className="divide-y divide-gray-100">
              {posts.map(p => (
                <div key={p.id} className="px-4 py-3 flex items-center gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-800 truncate">{p.content}</p>
                    <p className="text-xs text-gray-400 mt-0.5">{p.total_groups} 個社團 · 成功 {p.success_count} / 失敗 {p.fail_count}</p>
                  </div>
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium whitespace-nowrap ${
                    p.status === 'queued' ? 'bg-gray-100 text-gray-600' :
                    p.status === 'running' ? 'bg-blue-100 text-blue-700 animate-pulse' :
                    p.status === 'completed' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-600'
                  }`}>{p.status}</span>
                  {p.status === 'queued' && (
                    <button onClick={() => api.startPost(p.id).then(() => api.getPosts().then(setPosts))}
                      className="text-xs bg-blue-600 text-white px-2 py-1 rounded-lg hover:bg-blue-700">開始</button>
                  )}
                </div>
              ))}
              {posts.length === 0 && (
                <p className="px-4 py-8 text-center text-gray-400 text-sm">尚無發文任務</p>
              )}
            </div>
          </div>
        </div>

        <div>
          <LivePreview className="sticky top-4" accountId={selAccount || undefined} />
        </div>
      </div>
    </div>
  )
}
