'use client'
import { useState } from 'react'
import { usePathname } from 'next/navigation'
import LicenseGate from './LicenseGate'

const NAV_ITEMS = [
  { href: '/', icon: '🏠', label: 'Dashboard' },
  { href: '/studio', icon: '🎨', label: 'AI 工作室' },
  { href: '/accounts', icon: '👤', label: '帳號管理' },
  { href: '/groups', icon: '👥', label: '社團管理' },
  { href: '/posts', icon: '📝', label: '發文佇列' },
  { href: '/schedule', icon: '⏰', label: '排程' },
  { href: '/report', icon: '📊', label: '報表' },
  { href: '/remote', icon: '📱', label: '手機遙控' },
] as const

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const isActivate = pathname === '/activate'
  const [drawerOpen, setDrawerOpen] = useState(false)

  if (isActivate) {
    return (
      <LicenseGate>
        <main className="min-h-screen">{children}</main>
      </LicenseGate>
    )
  }

  return (
    <LicenseGate>
      <div className="flex min-h-screen">
        <DesktopSidebar />

        {drawerOpen && (
          <div
            className="fixed inset-0 z-40 bg-black/40 md:hidden"
            onClick={() => setDrawerOpen(false)}
            aria-hidden="true"
          />
        )}

        <div
          className={`fixed top-0 left-0 z-50 h-full w-64 transform bg-white shadow-xl transition-transform duration-300 ease-in-out md:hidden ${
            drawerOpen ? 'translate-x-0' : '-translate-x-full'
          }`}
          aria-hidden={!drawerOpen}
        >
          <MobileDrawer onClose={() => setDrawerOpen(false)} />
        </div>

        <div className="flex flex-1 flex-col">
          <Topbar onMenuClick={() => setDrawerOpen(true)} />
          <main className="flex-1 p-4 md:p-6 overflow-auto">{children}</main>
        </div>
      </div>
    </LicenseGate>
  )
}

function Topbar({ onMenuClick }: { onMenuClick: () => void }) {
  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-gray-200 bg-white px-4 md:hidden">
      <button
        type="button"
        onClick={onMenuClick}
        className="flex h-9 w-9 items-center justify-center rounded-lg text-gray-600 hover:bg-gray-100"
        aria-label="開啟選單"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="22"
          height="22"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <line x1="3" y1="6" x2="21" y2="6" />
          <line x1="3" y1="12" x2="21" y2="12" />
          <line x1="3" y1="18" x2="21" y2="18" />
        </svg>
      </button>

      <div className="flex items-center gap-2">
        <span className="text-base font-bold text-blue-600">FBPoster Pro</span>
      </div>

      <button
        type="button"
        className="flex h-9 w-9 items-center justify-center rounded-lg text-gray-600 hover:bg-gray-100"
        aria-label="切換主題"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
        </svg>
      </button>
    </header>
  )
}

function NavList({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname()
  return (
    <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
      {NAV_ITEMS.map(({ href, icon, label }) => {
        const active = pathname === href
        return (
          <a
            key={href}
            href={href}
            onClick={() => onNavigate?.()}
            className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors ${
              active
                ? 'bg-blue-50 text-blue-600'
                : 'text-gray-700 hover:bg-blue-50 hover:text-blue-600'
            }`}
          >
            <span>{icon}</span>
            <span>{label}</span>
          </a>
        )
      })}
    </nav>
  )
}

function Brand({ onClose }: { onClose?: () => void }) {
  return (
    <div className="flex items-center justify-between p-4 border-b border-gray-200">
      <div>
        <h1 className="text-lg font-bold text-blue-600">FBPoster Pro</h1>
        <p className="text-xs text-gray-500 mt-0.5">v1.1.0</p>
      </div>
      {onClose && (
        <button
          type="button"
          onClick={onClose}
          className="flex h-8 w-8 items-center justify-center rounded-lg text-gray-500 hover:bg-gray-100 md:hidden"
          aria-label="關閉選單"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      )}
    </div>
  )
}

function DesktopSidebar() {
  return (
    <aside className="hidden md:flex w-56 flex-col bg-white border-r border-gray-200 min-h-screen">
      <Brand />
      <NavList />
      <div className="p-3 border-t border-gray-200">
        <a href="/activate" className="text-xs text-gray-400 hover:text-gray-600">
          授權設定
        </a>
      </div>
    </aside>
  )
}

function MobileDrawer({ onClose }: { onClose: () => void }) {
  return (
    <aside className="flex h-full w-64 flex-col bg-white">
      <Brand onClose={onClose} />
      <NavList onNavigate={onClose} />
      <div className="p-3 border-t border-gray-200">
        <a href="/activate" className="text-xs text-gray-400 hover:text-gray-600">
          授權設定
        </a>
      </div>
    </aside>
  )
}
