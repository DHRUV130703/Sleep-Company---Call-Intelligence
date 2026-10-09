import { useQuery } from '@tanstack/react-query'
import { Search, X } from 'lucide-react'
import { useRef, useState } from 'react'
import { useSearchParams } from 'react-router'
import { Input } from '@/components/ui/input'
import { LEAD_FILTER_KEYS, leadsApi } from '@/lib/api-leads'
import { INTENT_LABELS, LEAD_STATUS_LABELS } from '@/lib/labels'
import { cn } from '@/lib/utils'
import { dateLabel } from '@/lib/leads-format'
import { DateRangeFilter, SourceFilter } from './filter-controls'

const AGENT_TYPES = [
  { value: '', label: 'All' },
  { value: 'ai', label: 'AI' }, // AI always on the left, Human on the right.
  { value: 'human', label: 'Human' },
]

/**
 * Filters for All Conversations (PRD §6.3): search, AI / Human, date and source (upload batch).
 * Active filters show as removable chips. Everything lives in the URL, so a filtered view can be
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

  const toggleSource = (id: string) => {
    const current = (new URLSearchParams(window.location.search).get('batch_id') ?? '').split(',').filter(Boolean)
    update({ batch_id: (current.includes(id) ? current.filter((x) => x !== id) : [...current, id]).join(',') })
  }

  const removeChip = (c: Chip) => {
    if (c.keys.includes('q')) setQuery('')
    update(Object.fromEntries(c.keys.map((k) => [k, ''])))
  }

  const clearAll = () => {
    window.clearTimeout(searchTimer.current)
    setQuery('')
    setParams(new URLSearchParams(), { replace: true })
  }

  const batches = options.data?.batches ?? []
  // Two batches can share a name (made in the same minute): add the batch number to tell them apart.
  const sources = batches.map((b) => ({
    value: String(b.id),
    label: batches.filter((x) => x.name === b.name).length > 1 ? `${b.name} · #${b.id}` : b.name,
  }))
  const selectedSources = (params.get('batch_id') ?? '').split(',').filter(Boolean)

  const from = params.get('date_from') ?? ''
  const to = params.get('date_to') ?? ''
  const chips = activeChips(params, from, to)

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
        <SourceFilter
          options={sources}
          selected={selectedSources}
          loading={options.isPending}
          onToggle={toggleSource}
          onClear={() => update({ batch_id: '' })}
        />
      </div>

      {chips.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5" aria-label="Active filters">
          {chips.map((c) => (
            <span key={`${c.name}-${c.label}`} className="inline-flex h-7 items-center gap-1 rounded-full border bg-surface pr-1 pl-3 text-[13px]">
              <span className="text-muted-foreground">{c.name}:</span>
              <span className="max-w-48 truncate font-medium">{c.label}</span>
              <button
                type="button"
                onClick={() => removeChip(c)}
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

function activeChips(params: URLSearchParams, from: string, to: string): Chip[] {
  const chips: Chip[] = []
  const q = params.get('q')
  if (q) chips.push({ name: 'Search', label: `“${q}”`, keys: ['q'] })
  const agent = params.get('agent_type')
  if (agent) chips.push({ name: 'Agent', label: agent === 'ai' ? 'AI voice bot' : 'Human', keys: ['agent_type'] })
  if (from || to) chips.push({ name: 'Date', label: dateLabel(from, to), keys: ['date_from', 'date_to'] })
  const intent = params.get('intent_bucket')
  if (intent) chips.push({ name: 'Intent', label: INTENT_LABELS[intent] ?? intent, keys: ['intent_bucket'] })
  // Sources are not shown as chips: the Source button already says what is picked.
  // Filters set elsewhere (KPI cards, an old shared link): still shown, so they can be removed.
  const names: Record<string, string> = { campaign: 'Campaign', owner: 'Owner', status: 'Status', status_category: 'Status category' }
  for (const k of LEAD_FILTER_KEYS) {
    const v = params.get(k)
    if (v && k !== 'batch_id' && !chips.some((c) => c.keys.includes(k))) {
      chips.push({ name: names[k] ?? k, label: k === 'status' ? (LEAD_STATUS_LABELS[v] ?? v) : v, keys: [k] })
    }
  }
  return chips
}
