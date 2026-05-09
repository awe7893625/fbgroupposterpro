'use client'
import { usePathname } from 'next/navigation'
import LicenseGate from './LicenseGate'

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const isActivate = pathname === '/activate'

  return (
    <LicenseGate>
      {isActivate ? (
        <main className="min-h-screen">{children}</main>
      ) : (
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="flex-1 p-6 overflow-auto">{children}</main>
        </div>
      )}
    </LicenseGate>
  )
}

function Sidebar() {
  return (
    <aside className="w-56 bg-white border-r border-gray-200 flex flex-col min-h-screen">
      <div className="p-4 border-b border-gray-200">
        <h1 className="text-lg font-bold text-blue-600">FBPoster Pro</h1>
        <p className="text-xs text-gray-500 mt-0.5">v1.1.0</p>
      </div>
      <nav className="flex-1 p-3 space-y-1">
        {[
          { href: '/', icon: '🏠', label: 'Dashboard' },
          { href: '/accounts', icon: '👤', label: '帳號管理' },
          { href: '/groups', icon: '👥', label: '社團管理' },
          { href: '/posts', icon: '📝', label: '發文佇列' },
          { href: '/schedule', icon: '⏰', label: '排程' },
          { href: '/report', icon: '📊', label: '報表' },
        ].map(({ href, icon, label }) => (
          <a key={href} href={href}
             className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-gray-700 hover:bg-blue-50 hover:text-blue-600 transition-colors">
            <span>{icon}</span>
            <span>{label}</span>
          </a>
        ))}
      </nav>
      <div className="p-3 border-t border-gray-200">
        <a href="/activate" className="text-xs text-gray-400 hover:text-gray-600">授權設定</a>
      </div>
    </aside>
  )
}
