import type { Metadata } from 'next'
import './globals.css'
import AppShell from '../components/AppShell'

export const metadata: Metadata = {
  title: 'FBGroupPoster Pro',
  description: '台灣房仲專屬 FB 社團自動發文工具',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-TW">
      <body className="bg-gray-50 min-h-screen">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  )
}
