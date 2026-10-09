// The two popover controls of the All Conversations filter bar: date range and "Filters".

import { CalendarDays, ChevronDown, SlidersHorizontal } from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { DATE_PRESETS, dateLabel, isoDay } from '@/lib/leads-format'
import { cn } from '@/lib/utils'

// ---------------------------------------------------------------------------
// Date range
// ---------------------------------------------------------------------------

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
// "Filters" popover: the less-used filters, each a labelled dropdown
// ---------------------------------------------------------------------------

export interface FilterField {
  key: string
  label: string
  value: string
  options: { value: string; label: string }[]
}

const ANY = 'any' // Radix Select can't use '' as a value.

export function MoreFilters({ fields, onChange, onClear }: { fields: FilterField[]; onChange: (key: string, value: string) => void; onClear: () => void }) {
  const count = fields.filter((f) => f.value).length
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" className={cn('h-9 bg-surface', count > 0 && 'border-foreground/40')}>
          <SlidersHorizontal className="size-4 text-muted-foreground" aria-hidden />
          Filters
          {count > 0 && (
            <span className="num grid size-5 place-items-center rounded-full bg-foreground text-[11px] font-semibold text-background">
              {count}
              <span className="sr-only"> active</span>
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-80 p-4">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="font-medium">Filters</h3>
          {count > 0 && (
            <Button variant="ghost" size="xs" onClick={onClear}>
              Clear
            </Button>
          )}
        </div>
        <div className="space-y-3">
          {fields.map((f) => (
            <label key={f.key} className="block">
              <span className="mb-1 block text-xs font-medium text-muted-foreground">{f.label}</span>
              <Select value={f.value || ANY} onValueChange={(v) => onChange(f.key, v === ANY ? '' : v)}>
                <SelectTrigger aria-label={f.label} className="w-full bg-surface">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ANY}>Any</SelectItem>
                  {f.options.map((o) => (
                    <SelectItem key={o.value} value={o.value}>
                      {o.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </label>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  )
}
