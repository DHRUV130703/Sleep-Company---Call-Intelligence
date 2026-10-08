import { useQuery } from '@tanstack/react-query'
import { Search, X } from 'lucide-react'
import { useRef, useState } from 'react'
import { useSearchParams } from 'react-router'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { LEAD_FILTER_KEYS, leadsApi } from '@/lib/api-leads'
import { LEAD_STATUS_LABELS } from '@/lib/labels'
import { isoDay } from '@/lib/leads-format'
import { cn } from '@/lib/utils'

const ALL = 'all' // Radix Select can't use '' as a value, so "All" is this sentinel.

const STATUS_CATEGORIES = [
  { value: 'in_progress', label: 'In Progress' },
  { value: 'won', label: 'Won' },
  { value: 'lost', label: 'Lost' },
]

const AGENT_TYPES = [
  { value: '', label: 'All' },
  { value: 'ai', label: 'AI' }, // AI always on the left, Human on the right.
  { value: 'human', label: 'Human' },
]

/**
 * Filters for All Conversations (PRD §6.3). Everything lives in the URL search params,
 * so a filtered view can be shared as a link. Changing a filter jumps back to page 1.
 */
export function FilterBar() {
  const [params, setParams] = useSearchParams()
  const options = useQuery({ queryKey: ['lead-filters'], queryFn: leadsApi.filterOptions })

  const setParam = (key: string, value: string) => {
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        if (value) next.set(key, value)
        else next.delete(key)
        next.delete('page')
        return next
      },
      { replace: true },
    )
  }

  // Customer search: typed locally, written to the URL after a short pause.
  const urlQuery = params.get('q') ?? ''
  const [query, setQuery] = useState(urlQuery)
  const [seenUrlQuery, setSeenUrlQuery] = useState(urlQuery)
  if (urlQuery !== seenUrlQuery) {
    // The URL changed from elsewhere (back button, "Reset all filters" link): follow it.
    setSeenUrlQuery(urlQuery)
    if (urlQuery !== query.trim()) setQuery(urlQuery)
  }
  const searchTimer = useRef<number | undefined>(undefined)
  const onSearch = (value: string) => {
    setQuery(value)
    window.clearTimeout(searchTimer.current)
    searchTimer.current = window.setTimeout(() => setParam('q', value.trim()), 300)
  }

  const hasFilters = LEAD_FILTER_KEYS.some((k) => params.get(k))
  const resetAll = () => {
    window.clearTimeout(searchTimer.current)
    setQuery('')
    setParams(new URLSearchParams(), { replace: true })
  }

  const setLast30Days = () => {
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.set('date_from', isoDay(-29))
        next.set('date_to', isoDay(0))
        next.delete('page')
        return next
      },
      { replace: true },
    )
  }

  const o = options.data
  return (
    <section aria-label="Filters" className="mb-6 flex flex-wrap items-end gap-2">
      <fieldset className="flex flex-wrap items-center gap-1.5 rounded-lg border bg-surface px-2 py-1">
        <legend className="sr-only">Date range</legend>
        <label className="sr-only" htmlFor="f-date-from">
          From date
        </label>
        <input
          id="f-date-from"
          type="date"
          value={params.get('date_from') ?? ''}
          max={params.get('date_to') ?? undefined}
          onChange={(e) => setParam('date_from', e.target.value)}
          className="num h-6 rounded bg-transparent text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        <span className="text-muted-foreground" aria-hidden>
          –
        </span>
        <label className="sr-only" htmlFor="f-date-to">
          To date
        </label>
        <input
          id="f-date-to"
          type="date"
          value={params.get('date_to') ?? ''}
          min={params.get('date_from') ?? undefined}
          onChange={(e) => setParam('date_to', e.target.value)}
          className="num h-6 rounded bg-transparent text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        <Button variant="ghost" size="xs" onClick={setLast30Days}>
          Last 30 days
        </Button>
      </fieldset>

      <div className="relative w-full sm:w-56">
        <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          type="search"
          aria-label="Search customer by name or phone"
          placeholder="Customer name or phone"
          value={query}
          onChange={(e) => onSearch(e.target.value)}
          className="bg-surface pl-8"
        />
      </div>

      <FilterSelect
        label="Conversation source"
        value={params.get('batch_id') ?? ''}
        onChange={(v) => setParam('batch_id', v)}
        options={(o?.batches ?? []).map((b) => ({ value: String(b.id), label: b.name }))}
      />
      <FilterSelect
        label="Campaign"
        value={params.get('campaign') ?? ''}
        onChange={(v) => setParam('campaign', v)}
        options={(o?.campaigns ?? []).map((c) => ({ value: c, label: c }))}
      />
      <FilterSelect
        label="Conversation owner"
        value={params.get('owner') ?? ''}
        onChange={(v) => setParam('owner', v)}
        options={(o?.owners ?? []).map((name) => ({ value: name, label: name }))}
      />

      <div role="group" aria-label="Agent type" className="flex h-8 items-center rounded-lg border bg-surface p-0.5">
        {AGENT_TYPES.map((t) => {
          const active = (params.get('agent_type') ?? '') === t.value
          return (
            <button
              key={t.label}
              type="button"
              aria-pressed={active}
              onClick={() => setParam('agent_type', t.value)}
              className={cn(
                'h-full rounded-md px-2.5 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring',
                active && t.value === 'ai' && 'bg-ai-soft text-ai',
                active && t.value === 'human' && 'bg-human-soft text-human',
                active && t.value === '' && 'bg-surface-sunken font-medium',
                !active && 'text-muted-foreground hover:text-foreground',
              )}
            >
              {t.label}
            </button>
          )
        })}
      </div>

      <FilterSelect
        label="Status"
        value={params.get('status') ?? ''}
        onChange={(v) => setParam('status', v)}
        options={(o?.statuses ?? []).map((s) => ({ value: s, label: LEAD_STATUS_LABELS[s] ?? s }))}
      />
      <FilterSelect
        label="Status category"
        value={params.get('status_category') ?? ''}
        onChange={(v) => setParam('status_category', v)}
        options={STATUS_CATEGORIES}
      />

      <Button variant="ghost" onClick={resetAll} disabled={!hasFilters}>
        <X />
        Reset all
      </Button>
    </section>
  )
}

interface FilterSelectProps {
  label: string
  value: string
  onChange: (value: string) => void
  options: { value: string; label: string }[]
}

/** A dropdown whose first option is "All <label>". Empty value = no filter. */
function FilterSelect({ label, value, onChange, options }: FilterSelectProps) {
  return (
    <Select value={value || ALL} onValueChange={(v) => onChange(v === ALL ? '' : v)}>
      <SelectTrigger aria-label={label} className={cn('max-w-56 bg-surface', value && 'border-ai text-ai')}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL}>{`All · ${label}`}</SelectItem>
        {options.map((opt) => (
          <SelectItem key={opt.value} value={opt.value}>
            {opt.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
