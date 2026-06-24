import type { Metadata } from 'next'
import './globals.css'
import AppShell from '../components/AppShell'
import QueryBootstrap from '../components/QueryBootstrap'

export const metadata: Metadata = {
  title: 'FBGroupPoster Pro',
  description: '台灣房仲專屬 FB 社團自動發文工具',
  themeColor: '#2563eb',
  manifest: '/manifest.json',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-TW">
      <head>
        <link rel="manifest" href="/manifest.json" />
        <meta name="theme-color" content="#2563eb" />
      </head>
      <body className="bg-gray-50 min-h-screen">
        <QueryBootstrap />
        <AppShell>{children}</AppShell>
      </body>
    </html>
  )
}
