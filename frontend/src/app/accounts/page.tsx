'use client'
import { useEffect, useState } from 'react'
import { api, Account } from '../../lib/api'

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [form, setForm] = useState({ name: '', email: '', password: '', proxy: '' })
  const [loading, setLoading] = useState(false)
  const [msg, setMsg] = useState('')

  const load = () => api.getAccounts().then(setAccounts).catch(console.error)
  useEffect(() => { load() }, [])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setMsg('')
    try {
      await api.createAccount({ name: form.name, email: form.email, password: form.password, proxy: form.proxy || undefined })
      setForm({ name: '', email: '', password: '', proxy: '' })
      setMsg('帳號已新增')
      load()
    } catch (e: any) {
      setMsg('錯誤：' + e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-800 mb-6">帳號管理</h2>

      <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm mb-6">
        <h3 className="font-semibold text-gray-700 mb-4">新增帳號</h3>
        <form onSubmit={submit} className="grid grid-cols-2 gap-3">
          <input required placeholder="帳號名稱" value={form.name} onChange={e => setForm(f => ({...f, name: e.target.value}))}
            className="col-span-2 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
          <input required type="email" placeholder="Email" value={form.email} onChange={e => setForm(f => ({...f, email: e.target.value}))}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
          <input required type="password" placeholder="密碼" value={form.password} onChange={e => setForm(f => ({...f, password: e.target.value}))}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
          <input placeholder="Proxy (選填) socks5://..." value={form.proxy} onChange={e => setForm(f => ({...f, proxy: e.target.value}))}
            className="col-span-2 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
          <button type="submit" disabled={loading}
            className="col-span-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors">
            {loading ? '新增中...' : '新增帳號'}
          </button>
        </form>
        {msg && <p className="mt-2 text-sm text-gray-600">{msg}</p>}
      </div>

      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-600">
            <tr>
              <th className="px-4 py-3 text-left">名稱</th>
              <th className="px-4 py-3 text-left">Email</th>
              <th className="px-4 py-3 text-left">狀態</th>
              <th className="px-4 py-3 text-left">Proxy</th>
              <th className="px-4 py-3 text-left">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {accounts.map(a => (
              <tr key={a.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-medium">{a.name}</td>
                <td className="px-4 py-3 text-gray-500">{a.email}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                    a.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-600'
                  }`}>{a.status}</span>
                </td>
                <td className="px-4 py-3 text-gray-400 text-xs">{a.proxy || '—'}</td>
                <td className="px-4 py-3">
                  <button onClick={() => api.deleteAccount(a.id).then(load)}
                    className="text-red-500 hover:text-red-700 text-xs">刪除</button>
                </td>
              </tr>
            ))}
            {accounts.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400">尚無帳號</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
