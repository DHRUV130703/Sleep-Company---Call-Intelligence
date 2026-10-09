import { useQuery } from '@tanstack/react-query'
import { Search, X } from 'lucide-react'
import { useRef, useState } from 'react'
import { useSearchParams } from 'react-router'
import { Input } from '@/components/ui/input'
import { LEAD_FILTER_KEYS, leadsApi } from '@/lib/api-leads'
import { INTENT_LABELS, LEAD_STATUS_LABELS } from '@/lib/labels'
import { cn } from '@/lib/utils'
import { dateLabel } from '@/lib/leads-format'
import { DateRangeFilter, type FilterField, MoreFilters } from './filter-controls'

const STATUS_CATEGORIES = [
  { value: 'in_progress', label: 'In progress' },
  { value: 'won', label: 'Won' },
  { value: 'lost', label: 'Lost' },
]

const AGENT_TYPES = [
  { value: '', label: 'All' },
  { value: 'ai', label: 'AI' }, // AI always on the left, Human on the right.
  { value: 'human', label: 'Human' },
]

const MORE_KEYS = ['batch_id', 'campaign', 'owner', 'status', 'status_category'] as const

/**
 * Filters for All Conversations (PRD §6.3): search, AI / Human, date, and a "Filters" popover for the
 * rest. Active filters show as removable chips. Everything lives in the URL, so a filtered view can be
 * shared as a link; changing a filter jumps back to page 1.
 */
export function FilterBar() {
  const [params, setParams] = useSearchParams()
  const options = useQuery({ queryKey: ['lead-filters'], queryFn: leadsApi.filterOptions })

  const update = (changes: Record<string, string>) => {
    // Start from the address bar, not this render's params: the search box updates after a pause, and by
    // then another filter (e.g. the date) may have changed.
    const next = new URLSearchParams(window.location.search)
    for (const [k, v] of Object.entries(changes)) {
      if (v) next.set(k, v)
      else next.delete(k)
    }
    next.delete('page')
    setParams(next, { replace: true })
  }

  // Customer search: typed locally, written to the URL after a short pause.
  const urlQuery = params.get('q') ?? ''
  const [query, setQuery] = useState(urlQuery)
  const [seenUrlQuery, setSeenUrlQuery] = useState(urlQuery)
  if (urlQuery !== seenUrlQuery) {
    // The URL changed from elsewhere (back button, a chip, "Clear all"): follow it.
    setSeenUrlQuery(urlQuery)
    if (urlQuery !== query.trim()) setQuery(urlQuery)
  }
  const searchTimer = useRef<number | undefined>(undefined)
  const onSearch = (value: string) => {
    setQuery(value)
    window.clearTimeout(searchTimer.current)
    searchTimer.current = window.setTimeout(() => update({ q: value.trim() }), 300)
  }

  const clearAll = () => {
    window.clearTimeout(searchTimer.current)
    setQuery('')
    setParams(new URLSearchParams(), { replace: true })
  }

  const o = options.data
  const fields: FilterField[] = [
    { key: 'batch_id', label: 'Source (batch)', value: params.get('batch_id') ?? '',
      options: (o?.batches ?? []).map((b) => ({ value: String(b.id), label: b.name })) },
    { key: 'campaign', label: 'Campaign', value: params.get('campaign') ?? '',
      options: (o?.campaigns ?? []).map((c) => ({ value: c, label: c })) },
    { key: 'owner', label: 'Owner', value: params.get('owner') ?? '',
      options: (o?.owners ?? []).map((n) => ({ value: n, label: n })) },
    { key: 'status', label: 'Status', value: params.get('status') ?? '',
      options: (o?.statuses ?? []).map((s) => ({ value: s, label: LEAD_STATUS_LABELS[s] ?? s })) },
    { key: 'status_category', label: 'Status category', value: params.get('status_category') ?? '',
      options: STATUS_CATEGORIES },
  ]

  const from = params.get('date_from') ?? ''
  const to = params.get('date_to') ?? ''
  const chips = activeChips(params, fields, from, to)

  return (
    <section aria-label="Filters" className="mb-6 space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative w-full sm:w-80">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input
            type="search"
            aria-label="Search by customer name or phone"
            placeholder="Search name or phone"
            value={query}
            onChange={(e) => onSearch(e.target.value)}
            className="h-9 bg-surface pl-9"
          />
        </div>

        <div role="group" aria-label="Agent type" className="flex h-9 items-center rounded-lg border bg-surface p-0.5">
          {AGENT_TYPES.map((t) => {
            const active = (params.get('agent_type') ?? '') === t.value
            return (
              <button
                key={t.label}
                type="button"
                aria-pressed={active}
                onClick={() => update({ agent_type: t.value })}
                className={cn(
                  'h-full rounded-md px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring',
                  active && t.value === 'ai' && 'bg-ai-soft font-medium text-ai',
                  active && t.value === 'human' && 'bg-human-soft font-medium text-human',
                  active && t.value === '' && 'bg-surface-sunken font-medium',
                  !active && 'text-muted-foreground hover:text-foreground',
                )}
              >
                {t.label}
              </button>
            )
          })}
        </div>

        <DateRangeFilter from={from} to={to} onChange={(f, t) => update({ date_from: f, date_to: t })} />
        <MoreFilters
          fields={fields}
          onChange={(key, value) => update({ [key]: value })}
          onClear={() => update(Object.fromEntries(MORE_KEYS.map((k) => [k, ''])))}
        />
      </div>

      {chips.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5" aria-label="Active filters">
          {chips.map((c) => (
            <span key={c.label} className="inline-flex h-7 items-center gap-1 rounded-full border bg-surface pr-1 pl-3 text-[13px]">
              <span className="text-muted-foreground">{c.name}:</span>
              <span className="max-w-48 truncate font-medium">{c.label}</span>
              <button
                type="button"
                onClick={() => (c.keys.includes('q') ? (setQuery(''), update({ q: '' })) : update(Object.fromEntries(c.keys.map((k) => [k, '']))))}
                aria-label={`Remove filter ${c.name}: ${c.label}`}
                className="grid size-5 place-items-center rounded-full text-muted-foreground hover:bg-accent hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring"
              >
                <X className="size-3" aria-hidden />
              </button>
            </span>
          ))}
          {chips.length > 1 && (
            <button
              type="button"
              onClick={clearAll}
              className="ml-1 rounded-sm px-1 text-[13px] text-muted-foreground underline-offset-4 hover:text-foreground hover:underline focus-visible:outline-2 focus-visible:outline-ring"
            >
              Clear all
            </button>
          )}
        </div>
      )}
    </section>
  )
}

interface Chip {
  name: string
  label: string
  keys: string[] // URL params this chip clears
}

function activeChips(params: URLSearchParams, fields: FilterField[], from: string, to: string): Chip[] {
  const chips: Chip[] = []
  const q = params.get('q')
  if (q) chips.push({ name: 'Search', label: `“${q}”`, keys: ['q'] })
  const agent = params.get('agent_type')
  if (agent) chips.push({ name: 'Agent', label: agent === 'ai' ? 'AI voice bot' : 'Human', keys: ['agent_type'] })
  if (from || to) chips.push({ name: 'Date', label: dateLabel(from, to), keys: ['date_from', 'date_to'] })
  for (const f of fields) {
    if (f.value) chips.push({ name: f.label, label: f.options.find((o) => o.value === f.value)?.label ?? f.value, keys: [f.key] })
  }
  const intent = params.get('intent_bucket')
  if (intent) chips.push({ name: 'Intent', label: INTENT_LABELS[intent] ?? intent, keys: ['intent_bucket'] })
  // Any other filter key we don't label (keeps "Clear all" honest).
  for (const k of LEAD_FILTER_KEYS) {
    if (params.get(k) && !chips.some((c) => c.keys.includes(k))) chips.push({ name: k, label: params.get(k)!, keys: [k] })
  }
  return chips
}
