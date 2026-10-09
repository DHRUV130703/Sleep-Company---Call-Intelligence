import {
  AudioLines,
  GitCompareArrows,
  Layers,
  MessagesSquare,
  Phone,
  Settings,
  Upload,
  type LucideIcon,
} from 'lucide-react'
import { NavLink } from 'react-router'
import { PRODUCT_AUTHOR, WORKSPACE_NAME, WORKSPACE_SUBTITLE } from '@/lib/constants'
import { cn } from '@/lib/utils'

interface NavItem {
  to: string
  label: string
  icon: LucideIcon
}

// Sidebar order follows PRD §5.
const NAV: NavItem[] = [
  { to: '/upload', label: 'Upload', icon: Upload },
  { to: '/batches', label: 'Batches', icon: Layers },
  { to: '/leads', label: 'All Conversations', icon: MessagesSquare },
  { to: '/calls', label: 'Calls', icon: Phone },
  { to: '/compare', label: 'AI vs Human', icon: GitCompareArrows },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav aria-label="Main" className="flex h-full w-64 flex-col border-r bg-sidebar">
      <div className="flex items-center gap-3 px-5 pt-5 pb-6">
        <div className="grid size-10 shrink-0 place-items-center rounded-lg bg-foreground text-background">
          <AudioLines className="size-5" aria-hidden />
        </div>
        <div className="min-w-0">
          <div className="truncate text-[15px] font-semibold leading-tight">{WORKSPACE_NAME}</div>
          <div className="truncate text-xs text-muted-foreground">{WORKSPACE_SUBTITLE}</div>
        </div>
      </div>

      <div className="px-5 pb-2 text-xs font-medium text-muted-foreground">Platform</div>
      <ul className="flex flex-col gap-0.5 px-3">
        {NAV.map(({ to, label, icon: Icon }) => (
          <li key={to}>
            <NavLink
              to={to}
              onClick={onNavigate}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-lg border border-transparent px-3 py-2 text-[14px] text-foreground/80 transition-colors',
                  'hover:bg-sidebar-accent hover:text-foreground',
                  'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring',
                  isActive && 'border-border bg-sidebar-accent font-medium text-foreground',
                )
              }
            >
              <Icon className="size-[18px] shrink-0" aria-hidden />
              {label}
            </NavLink>
          </li>
        ))}
      </ul>

      <SidebarFooter />
    </nav>
  )
}

function SidebarFooter() {
  return (
    <div className="mt-auto border-t px-5 py-4 text-[13px] text-muted-foreground">
      Product by <span className="font-medium text-foreground">{PRODUCT_AUTHOR}</span>
    </div>
  )
}
