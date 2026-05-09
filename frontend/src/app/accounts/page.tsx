'use client'
import { useEffect, useState } from 'react'
import { api, onboard, Account } from '../../lib/api'

const PLATFORMS: { id: 'fb' | 'threads' | 'instagram' | 'x'; label: string }[] = [
  { id: 'fb',        label: 'Facebook' },
  { id: 'threads',   label: 'Threads' },
  { id: 'instagram', label: 'Instagram' },
  { id: 'x',         label: 'X (Twitter)' },
]

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [form, setForm] = useState({ name: '', email: '', proxy: '' })
  const [creating, setCreating] = useState(false)
  const [createMsg, setCreateMsg] = useState('')

  // Per-account login state
  const [loggingIn, setLoggingIn] = useState<Record<number, boolean>>({})
  const [loginPlatform, setLoginPlatform] = useState<Record<number, string>>({})
  const [loginMsg, setLoginMsg] = useState<Record<number, string>>({})

  const load = () => api.getAccounts().then(setAccounts).catch(console.error)
  useEffect(() => { load() }, [])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreating(true); setCreateMsg('')
    try {
      await api.createAccount({ name: form.name, email: form.email, password: '', proxy: form.proxy || undefined })
      setForm({ name: '', email: '', proxy: '' })
      setCreateMsg('帳號已新增。請按「登入 FB」完成首次授權。')
      load()
    } catch (e: any) {
      setCreateMsg('錯誤：' + e.message)
    } finally {
      setCreating(false)
    }
  }

  const startLogin = async (accountId: number) => {
    const platform = loginPlatform[accountId] || 'fb'
    setLoggingIn(s => ({ ...s, [accountId]: true }))
    setLoginMsg(s => ({ ...s, [accountId]: '🔓 已開啟瀏覽器視窗，請手動登入並通過任何 2FA / checkpoint。系統會自動偵測登入完成（最多等 10 分鐘）。' }))
    try {
      const r = await onboard.startLogin(accountId, platform)
      if (r.success) {
        setLoginMsg(s => ({ ...s, [accountId]: `✅ 登入完成！已儲存 ${r.cookie_count} 筆 cookies` }))
      } else {
        setLoginMsg(s => ({ ...s, [accountId]: '❌ ' + (r.error || '登入失敗') }))
      }
    } catch (e: any) {
      setLoginMsg(s => ({ ...s, [accountId]: '❌ ' + e.message }))
    } finally {
      setLoggingIn(s => ({ ...s, [accountId]: false }))
      load()
    }
  }

  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-800 mb-6">帳號管理</h2>

      <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm mb-6">
        <h3 className="font-semibold text-gray-700 mb-1">新增帳號</h3>
        <p className="text-xs text-gray-500 mb-4">不需要輸入密碼 — 新增後按「登入 FB」會開瀏覽器讓您手動登入，系統會記住登入狀態。</p>
        <form onSubmit={submit} className="grid grid-cols-2 gap-3">
          <input required placeholder="顯示名稱（如：北區業務帳號）" value={form.name} onChange={e => setForm(f => ({...f, name: e.target.value}))}
            className="col-span-2 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
          <input required type="email" placeholder="此帳號的 Email" value={form.email} onChange={e => setForm(f => ({...f, email: e.target.value}))}
            className="col-span-2 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
          <input placeholder="Proxy（選填）socks5://..." value={form.proxy} onChange={e => setForm(f => ({...f, proxy: e.target.value}))}
            className="col-span-2 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
          <button type="submit" disabled={creating}
            className="col-span-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors">
            {creating ? '新增中...' : '新增帳號'}
          </button>
        </form>
        {createMsg && <p className="mt-2 text-sm text-gray-600">{createMsg}</p>}
      </div>

      <div className="space-y-3">
        {accounts.map(a => (
          <div key={a.id} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-medium text-gray-800">{a.name}</span>
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                    a.logged_in ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'
                  }`}>{a.logged_in ? '✓ 已登入' : '尚未登入'}</span>
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                    a.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-600'
                  }`}>{a.status}</span>
                </div>
                <div className="text-xs text-gray-500 mt-1">{a.email}{a.proxy ? ` · proxy: ${a.proxy}` : ''}</div>
                {a.last_used_at && <div className="text-xs text-gray-400 mt-0.5">上次使用：{new Date(a.last_used_at).toLocaleString('zh-TW')}</div>}
              </div>
              <div className="flex items-center gap-2">
                <select value={loginPlatform[a.id] || 'fb'} onChange={e => setLoginPlatform(s => ({ ...s, [a.id]: e.target.value }))}
                  className="text-xs border border-gray-300 rounded px-2 py-1.5">
                  {PLATFORMS.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
                </select>
                <button onClick={() => startLogin(a.id)} disabled={loggingIn[a.id]}
                  className="text-xs bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded px-3 py-1.5 font-medium">
                  {loggingIn[a.id] ? '登入中...' : (a.logged_in ? '重新登入' : '登入 FB')}
                </button>
                <button onClick={() => api.deleteAccount(a.id).then(load)}
                  className="text-xs text-red-500 hover:text-red-700">刪除</button>
              </div>
            </div>
            {loginMsg[a.id] && <div className="mt-3 text-xs bg-gray-50 border border-gray-200 rounded p-2 text-gray-700">{loginMsg[a.id]}</div>}
          </div>
        ))}
        {accounts.length === 0 && (
          <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-400 shadow-sm">
            尚無帳號。請先新增帳號，再按「登入 FB」完成首次授權。
          </div>
        )}
      </div>
    </div>
  )
}
