// The date range control of the All Conversations filter bar: presets plus a custom range.

import { CalendarDays, ChevronDown } from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { DATE_PRESETS, dateLabel, isoDay } from '@/lib/leads-format'
import { cn } from '@/lib/utils'

interface DateRangeProps {
  from: string
  to: string
  onChange: (from: string, to: string) => void
}

export function DateRangeFilter({ from, to, onChange }: DateRangeProps) {
  const [open, setOpen] = useState(false)
  const active = Boolean(from || to)
  const pick = (f: string, t: string) => {
    onChange(f, t)
    setOpen(false)
  }
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" className={cn('h-9 bg-surface', active && 'border-foreground/40')}>
          <CalendarDays className="size-4 text-muted-foreground" aria-hidden />
          <span className="num">{dateLabel(from, to)}</span>
          <ChevronDown className="size-3.5 opacity-60" aria-hidden />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-80 p-2">
        <ul className="space-y-0.5">
          {[{ label: 'Any date', from: null }, ...DATE_PRESETS].map((p) => {
            const f = p.from === null ? '' : isoDay(p.from)
            const t = p.from === null ? '' : isoDay(0)
            const selected = f === from && t === to
            return (
              <li key={p.label}>
                <button
                  type="button"
                  onClick={() => pick(f, t)}
                  aria-pressed={selected}
                  className={cn(
                    'w-full rounded-md px-2.5 py-1.5 text-left text-sm hover:bg-accent focus-visible:outline-2 focus-visible:outline-ring',
                    selected && 'bg-accent font-medium',
                  )}
                >
                  {p.label}
                </button>
              </li>
            )
          })}
        </ul>
        <div className="mt-2 border-t px-1 pt-3 pb-1">
          <div className="mb-2 text-xs font-medium text-muted-foreground">Custom range</div>
          <div className="grid grid-cols-2 gap-2">
            <label className="text-xs text-muted-foreground">
              From
              <input
                type="date"
                value={from}
                max={to || undefined}
                onChange={(e) => onChange(e.target.value, to)}
                className="num mt-1 h-8 w-full rounded-md border bg-surface px-2 text-sm text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </label>
            <label className="text-xs text-muted-foreground">
              To
              <input
                type="date"
                value={to}
                min={from || undefined}
                onChange={(e) => onChange(from, e.target.value)}
                className="num mt-1 h-8 w-full rounded-md border bg-surface px-2 text-sm text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </label>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  )
}
