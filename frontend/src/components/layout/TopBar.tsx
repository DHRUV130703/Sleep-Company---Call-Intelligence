import { useQuery } from '@tanstack/react-query'
import { Monitor, Moon, PanelLeft, Sun, TriangleAlert } from 'lucide-react'
import { Link } from 'react-router'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { api } from '@/lib/api'
import { useTheme } from '@/lib/theme'

interface Props {
  title: string
  onToggleSidebar: () => void
}

export function TopBar({ title, onToggleSidebar }: Props) {
  const { pref, cycle } = useTheme()
  const ThemeIcon = pref === 'dark' ? Moon : pref === 'light' ? Sun : Monitor

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b bg-surface/90 px-4 backdrop-blur md:px-6">
      <Button variant="ghost" size="icon" onClick={onToggleSidebar} aria-label="Toggle sidebar">
        <PanelLeft className="size-5" />
      </Button>
      <div className="h-5 w-px bg-border" aria-hidden />
      <h1 className="truncate text-[15px] font-medium">{title}</h1>

      <div className="ml-auto flex items-center gap-2">
        <HealthAlert />
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="outline" size="icon" onClick={cycle} aria-label={`Theme: ${pref}. Click to change.`}>
              <ThemeIcon className="size-[18px]" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Theme: {pref}</TooltipContent>
        </Tooltip>
      </div>
    </header>
  )
}

/** Shows a warning button when any health check fails (e.g. worker stopped). Links to Settings. */
function HealthAlert() {
  const health = useQuery({ queryKey: ['health'], queryFn: api.health, refetchInterval: 15_000 })
  const failing = health.data?.checks.filter((c) => c.state === 'fail') ?? []
  const unreachable = health.isError

  if (!unreachable && failing.length === 0) return null
  const message = unreachable
    ? "Can't reach the server"
    : failing.map((c) => `${c.label}: ${c.detail}`).join(' · ')

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button variant="outline" size="icon" asChild className="border-warning/40 text-warning">
          <Link to="/settings" aria-label={`System problem: ${message}. Open settings.`}>
            <TriangleAlert className="size-[18px]" />
          </Link>
        </Button>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs">{message}</TooltipContent>
    </Tooltip>
  )
}
