'use client'
import { useEffect } from 'react'

/**
 * On mount, reads `token` and `api` from the URL query string and persists them
 * to localStorage (keys: `remote_token`, `remote_api_base`). Then strips those params from the URL
 * while preserving the pathname. Also registers the service worker. Renders nothing.
 */
export default function QueryBootstrap() {
  useEffect(() => {
    if (typeof window === 'undefined') return

    // Handle query params
    const params = new URLSearchParams(window.location.search)
    let changed = false

    const token = params.get('token')
    if (token) {
      localStorage.setItem('remote_token', token)
      params.delete('token')
      changed = true
    }

    const api = params.get('api')
    if (api) {
      localStorage.setItem('remote_api_base', api)
      params.delete('api')
      changed = true
    }

    if (changed) {
      const qs = params.toString()
      const next = qs
        ? `${window.location.pathname}?${qs}`
        : window.location.pathname
      window.history.replaceState(null, '', next)
    }

    // Register service worker
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js').catch(() => {
        // SW registration failed; app still works
      })
    }
  }, [])

  return null
}
