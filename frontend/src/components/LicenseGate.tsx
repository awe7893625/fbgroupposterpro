'use client'
import { useEffect, useState } from 'react'
import { api, LicenseStatus } from '../lib/api'

/**
 * Wraps the main app shell. On mount and on every route change, checks license status.
 * If not valid, redirects to /activate (unless already there).
 *
 * Children render unblocked once `valid` is confirmed; while checking, shows a spinner.
 * Errors fetching status (backend offline) render children anyway — Dashboard already
 * shows a "後端離線" banner in that case.
 */
export default function LicenseGate({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<LicenseStatus | null>(null)
  const [checking, setChecking] = useState(true)
  const [networkError, setNetworkError] = useState(false)

  useEffect(() => {
    let cancelled = false
    const path = typeof window !== 'undefined' ? window.location.pathname : '/'

    api.licenseStatus()
      .then(s => {
        if (cancelled) return
        setStatus(s)
        if (!s.valid && path !== '/activate') {
          window.location.replace('/activate')
        }
      })
      .catch(() => {
        if (cancelled) return
        setNetworkError(true)
      })
      .finally(() => { if (!cancelled) setChecking(false) })

    return () => { cancelled = true }
  }, [])

  if (checking) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
          <p className="text-sm text-gray-500">驗證授權中...</p>
        </div>
      </div>
    )
  }

  // Allow rendering even if backend is offline — Dashboard shows its own banner.
  if (networkError) return <>{children}</>

  // If invalid and not already on /activate, the redirect above handles it. Render placeholder.
  const path = typeof window !== 'undefined' ? window.location.pathname : '/'
  if (status && !status.valid && path !== '/activate') {
    return null
  }

  return <>{children}</>
}
