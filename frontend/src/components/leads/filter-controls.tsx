// Popover controls of the All Conversations filter bar: date range (presets + custom) and source batches.

import { CalendarDays, ChevronDown, Layers } from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
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

// ---------------------------------------------------------------------------
// Source: pick one or more upload batches
// ---------------------------------------------------------------------------

interface SourceOption {
  value: string
  label: string
}

interface SourceFilterProps {
  options: SourceOption[]
  selected: string[]
  /** Add or remove one batch. (The parent applies it to the current URL, so quick clicks never undo each other.) */
  onToggle: (value: string) => void
  onClear: () => void
  loading?: boolean
}

export function SourceFilter({ options, selected, onToggle, onClear, loading }: SourceFilterProps) {
  const [find, setFind] = useState('')
  const shown = find ? options.filter((o) => o.label.toLowerCase().includes(find.toLowerCase())) : options
  const label =
    selected.length === 0
      ? 'All sources'
      : selected.length === 1
        ? (options.find((o) => o.value === selected[0])?.label ?? '1 source')
        : `${selected.length} sources`

  return (
    <Popover onOpenChange={(open) => !open && setFind('')}>
      <PopoverTrigger asChild>
        <Button variant="outline" className={cn('h-9 max-w-64 bg-surface', selected.length > 0 && 'border-foreground/40')}>
          <Layers className="size-4 text-muted-foreground" aria-hidden />
          <span className="truncate">{label}</span>
          <ChevronDown className="size-3.5 opacity-60" aria-hidden />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-72 p-0">
        {options.length > 8 && (
          <div className="border-b p-2">
            <input
              type="search"
              value={find}
              onChange={(e) => setFind(e.target.value)}
              placeholder="Find a batch"
              aria-label="Find a batch"
              className="h-8 w-full rounded-md border bg-surface px-2.5 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </div>
        )}
        <ul className="max-h-72 overflow-y-auto p-1" aria-label="Sources">
          {shown.length === 0 && (
            <li className="px-2.5 py-2 text-sm text-muted-foreground">{loading ? 'Loading batches…' : 'No batch matches.'}</li>
          )}
          {shown.map((o) => {
            const checked = selected.includes(o.value)
            return (
              <li key={o.value}>
                <label className="flex cursor-pointer items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm hover:bg-accent">
                  <Checkbox checked={checked} onCheckedChange={() => onToggle(o.value)} />
                  <span className="truncate">{o.label}</span>
                </label>
              </li>
            )
          })}
        </ul>
        <div className="flex items-center justify-between border-t px-3 py-2 text-xs text-muted-foreground">
          <span className="num">{selected.length ? `${selected.length} selected` : 'Showing all sources'}</span>
          {selected.length > 0 && (
            <Button variant="ghost" size="xs" onClick={onClear}>
              Clear
            </Button>
          )}
        </div>
      </PopoverContent>
    </Popover>
  )
}
