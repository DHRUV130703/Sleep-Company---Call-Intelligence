import { useState } from 'react'
import { Outlet, useMatches } from 'react-router'
import { readPref, writePref } from '@/lib/storage'
import { cn } from '@/lib/utils'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'

const DESKTOP = '(min-width: 1024px)'

/** Page frame: sidebar on the left, top bar, page content. Each route sets its title via `handle.title`. */
export function AppShell() {
  const [collapsed, setCollapsed] = useState(() => readPref('sidebarCollapsed', false))
  const [mobileOpen, setMobileOpen] = useState(false)

  const matches = useMatches()
  const handle = matches.at(-1)?.handle as { title?: string } | undefined
  const title = handle?.title ?? 'LimeZip'

  const toggle = () => {
    if (window.matchMedia(DESKTOP).matches) {
      setCollapsed((c) => {
        writePref('sidebarCollapsed', !c)
        return !c
      })
    } else {
      setMobileOpen((o) => !o)
    }
  }

  return (
    <div className="flex min-h-dvh">
      {/* Desktop: in-flow, collapsible */}
      <aside className={cn('sticky top-0 hidden h-dvh shrink-0 lg:block', collapsed && 'lg:hidden')}>
        <Sidebar />
      </aside>

      {/* Mobile / tablet: off-canvas drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            className="absolute inset-0 bg-black/30"
            aria-label="Close menu"
            onClick={() => setMobileOpen(false)}
          />
          <div className="relative h-full w-64 shadow-xl animate-in slide-in-from-left duration-200">
            <Sidebar onNavigate={() => setMobileOpen(false)} />
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar title={title} onToggleSidebar={toggle} />
        <main className="mx-auto w-full max-w-[1440px] flex-1 px-4 py-6 md:px-6 lg:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
