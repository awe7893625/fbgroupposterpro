'use client'
import { useEffect, useState } from 'react'
import { api, LicenseStatus } from '../../lib/api'

const PLAN_OPTIONS: { id: 'basic' | 'pro' | 'premium'; name: string; price: number; tagline: string; perks: string[] }[] = [
  { id: 'basic',   name: '基礎版',   price: 299, tagline: '入門必備',     perks: ['1 個 FB 帳號', '50 個社團', '排程發文'] },
  { id: 'pro',     name: '專業版',   price: 599, tagline: '最受歡迎',     perks: ['3 個 FB 帳號', '無上限社團', 'AI 文案', '多平台（Threads/X/IG）'] },
  { id: 'premium', name: '旗艦版',   price: 999, tagline: '房仲團隊適用', perks: ['10 個 FB 帳號', '專屬客服', '優先功能', 'Pro 全部功能'] },
]

export default function ActivatePage() {
  const [status, setStatus] = useState<LicenseStatus | null>(null)
  const [tab, setTab] = useState<'activate' | 'trial' | 'buy'>('activate')

  // Activate form
  const [licenseKey, setLicenseKey] = useState('')
  const [activating, setActivating] = useState(false)
  const [activateMsg, setActivateMsg] = useState('')

  // Trial form
  const [trialEmail, setTrialEmail] = useState('')
  const [trialMsg, setTrialMsg] = useState('')
  const [trialing, setTrialing] = useState(false)

  // Buy form
  const [buyEmail, setBuyEmail] = useState('')

  const refresh = async () => {
    try { setStatus(await api.licenseStatus()) } catch {}
  }
  useEffect(() => { refresh() }, [])

  const submitActivate = async (e: React.FormEvent) => {
    e.preventDefault()
    setActivating(true); setActivateMsg('')
    try {
      const result = await api.licenseActivate(licenseKey)
      if (result.valid) {
        setActivateMsg('✅ 啟用成功！3 秒後跳轉到首頁...')
        setTimeout(() => { window.location.href = '/' }, 3000)
      } else {
        setActivateMsg('❌ ' + (result.error || '啟用失敗'))
      }
    } catch (e: any) {
      setActivateMsg('❌ ' + e.message)
    } finally {
      setActivating(false)
      refresh()
    }
  }

  const submitTrial = async (e: React.FormEvent) => {
    e.preventDefault()
    setTrialing(true); setTrialMsg('')
    try {
      const result = await api.licenseTrial(trialEmail)
      if (result.success) {
        setTrialMsg(`✅ ${result.message || '授權碼已寄到您的 Email'}，請收信後填入左邊啟用`)
        setTab('activate')
      } else {
        setTrialMsg('❌ ' + (result.error || '申請失敗'))
      }
    } catch (e: any) {
      setTrialMsg('❌ ' + e.message)
    } finally {
      setTrialing(false)
    }
  }

  const buy = async (plan: 'basic' | 'pro' | 'premium') => {
    try {
      const { url } = await api.licensePurchaseUrl(plan, buyEmail)
      window.open(url, '_blank', 'noopener,noreferrer')
    } catch (e: any) {
      alert('開啟付款頁面失敗：' + e.message)
    }
  }

  const activated = status?.valid

  return (
    <div className="max-w-3xl mx-auto px-4 py-10">
      <div className="text-center mb-8">
        <h1 className="text-3xl font-bold text-gray-800">FBGroupPosterPro</h1>
        <p className="text-gray-500 mt-1">台灣房仲專屬 FB 社團自動發文工具</p>
      </div>

      {/* current status banner */}
      {status && (
        <div className={`mb-6 rounded-xl border p-4 ${activated ? 'bg-green-50 border-green-200' : 'bg-amber-50 border-amber-200'}`}>
          {activated ? (
            <div className="text-sm text-green-800">
              已啟用 — <b>{status.plan}</b>，到期：{status.expires_at?.slice(0, 10)}
              <button onClick={() => location.assign('/')} className="ml-3 text-blue-600 underline">前往控制台 →</button>
            </div>
          ) : (
            <div className="text-sm text-amber-800">
              尚未啟用 {status.error ? `(${status.error})` : ''}。請輸入授權碼、申請試用或購買訂閱。
              <span className="ml-2 text-xs text-amber-600">裝置碼：{status.device_id?.slice(0, 8)}...</span>
            </div>
          )}
        </div>
      )}

      {/* tab switch */}
      <div className="flex gap-2 border-b border-gray-200 mb-6">
        {([['activate', '輸入授權碼'], ['trial', '免費試用 1 天'], ['buy', '購買訂閱']] as const).map(([id, label]) => (
          <button key={id} onClick={() => setTab(id)}
            className={`px-4 py-2 text-sm font-medium -mb-px border-b-2 transition-colors ${
              tab === id ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}>{label}</button>
        ))}
      </div>

      {tab === 'activate' && (
        <form onSubmit={submitActivate} className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
          <label className="block text-sm font-medium text-gray-700 mb-2">授權碼</label>
          <input required value={licenseKey} onChange={e => setLicenseKey(e.target.value.toUpperCase())}
            placeholder="FBP-XXXX-XXXX-XXXX"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 font-mono tracking-wider focus:ring-2 focus:ring-blue-500 outline-none" />
          <p className="text-xs text-gray-500 mt-2">
            授權碼會在購買後寄到您的 Email；首次啟用會綁定本台電腦。
          </p>
          <button type="submit" disabled={activating}
            className="mt-4 w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg px-4 py-2.5 font-medium transition-colors">
            {activating ? '驗證中...' : '啟用'}
          </button>
          {activateMsg && <p className="mt-3 text-sm">{activateMsg}</p>}
        </form>
      )}

      {tab === 'trial' && (
        <form onSubmit={submitTrial} className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
          <label className="block text-sm font-medium text-gray-700 mb-2">您的 Email</label>
          <input required type="email" value={trialEmail} onChange={e => setTrialEmail(e.target.value)}
            placeholder="you@example.com"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 outline-none" />
          <p className="text-xs text-gray-500 mt-2">
            試用 24 小時，每個 Email 與 IP 各只能申請一次。
          </p>
          <button type="submit" disabled={trialing}
            className="mt-4 w-full bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-lg px-4 py-2.5 font-medium transition-colors">
            {trialing ? '申請中...' : '申請試用'}
          </button>
          {trialMsg && <p className="mt-3 text-sm">{trialMsg}</p>}
        </form>
      )}

      {tab === 'buy' && (
        <div>
          <div className="bg-white rounded-xl border border-gray-200 p-4 mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">您的 Email（授權碼會寄到這裡）</label>
            <input type="email" value={buyEmail} onChange={e => setBuyEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 outline-none" />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {PLAN_OPTIONS.map(p => (
              <div key={p.id} className={`bg-white rounded-xl border p-5 shadow-sm ${p.id === 'pro' ? 'border-blue-500 ring-1 ring-blue-200' : 'border-gray-200'}`}>
                <div className="text-xs font-medium text-gray-500">{p.tagline}</div>
                <div className="mt-1 text-xl font-bold text-gray-800">{p.name}</div>
                <div className="mt-2 text-3xl font-bold text-gray-900">NT$ {p.price}<span className="text-sm font-normal text-gray-500"> / 月</span></div>
                <ul className="mt-4 space-y-1.5 text-sm text-gray-600">
                  {p.perks.map(perk => <li key={perk} className="flex gap-1.5"><span className="text-green-600">✓</span>{perk}</li>)}
                </ul>
                <button onClick={() => buy(p.id)}
                  className={`mt-5 w-full rounded-lg px-4 py-2 font-medium transition-colors ${
                    p.id === 'pro'
                      ? 'bg-blue-600 hover:bg-blue-700 text-white'
                      : 'bg-gray-800 hover:bg-gray-900 text-white'
                  }`}>
                  使用綠界付款
                </button>
              </div>
            ))}
          </div>
          <p className="text-center text-xs text-gray-500 mt-4">付款完成後，授權碼會自動寄到您的 Email。</p>
        </div>
      )}
    </div>
  )
}
