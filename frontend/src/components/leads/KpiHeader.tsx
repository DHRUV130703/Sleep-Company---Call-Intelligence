import { useQuery } from '@tanstack/react-query'
import { ArrowDownRight, ArrowUpRight } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { leadsApi, type LeadFilters } from '@/lib/api-leads'
import { formatHoursMins } from '@/lib/format'
import { INTENT_LABELS } from '@/lib/labels'
import type { IntentCounts, LeadKpis } from '@/lib/types-leads'
import { cn } from '@/lib/utils'

const BUCKETS: (keyof IntentCounts)[] = ['high', 'moderate', 'neutral', 'low', 'not_qualified', 'not_available']

const BUCKET_TEXT: Record<keyof IntentCounts, string> = {
  high: 'text-intent-high',
  moderate: 'text-intent-moderate',
  neutral: 'text-intent-neutral',
  low: 'text-intent-low',
  not_qualified: 'text-muted-foreground',
  not_available: 'text-muted-foreground',
}

interface Props {
  filters: LeadFilters
  selectedBucket: string
  onSelectBucket: (bucket: string) => void
}

/** KPI card, lead summary row and intent bucket cards at the top of All Conversations (PRD §6.3). */
export function KpiHeader({ filters, selectedBucket, onSelectBucket }: Props) {
  // Bucket counts must not depend on the bucket you picked, so the intent filter is left out.
  const { intent_bucket: _ignored, ...params } = filters
  const kpis = useQuery({ queryKey: ['lead-kpis', params], queryFn: () => leadsApi.kpis(params) })

  if (kpis.isPending) return <KpiSkeleton />
  if (kpis.isError) {
    return (
      <p role="alert" className="mb-6 rounded-lg bg-negative-soft px-3 py-2 text-negative">
        {kpis.error.message}
      </p>
    )
  }
  const k = kpis.data
  return (
    <div className="mb-6 space-y-4">
      <div className="grid gap-4 lg:grid-cols-[1fr_minmax(0,26rem)]">
        <LeadSummary k={k} />
        <ConversationsCard k={k} />
      </div>
      <ul className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {BUCKETS.map((b) => {
          const selected = selectedBucket === b
          return (
            <li key={b}>
              <button
                type="button"
                aria-pressed={selected}
                onClick={() => onSelectBucket(selected ? '' : b)}
                className={cn(
                  'w-full rounded-xl border bg-surface p-4 text-left outline-none transition-colors hover:bg-surface-sunken focus-visible:ring-2 focus-visible:ring-ring',
                  selected && 'border-ai ring-1 ring-ai',
                )}
              >
                <div className={cn('text-sm font-medium', BUCKET_TEXT[b])}>{INTENT_LABELS[b]}</div>
                <div className="mt-1 flex items-baseline justify-between gap-2">
                  <span className="num text-2xl font-semibold">{k.intent[b].toLocaleString()}</span>
                  {k.has_previous_period && <Delta value={k.deltas.intent?.[b] ?? null} />}
                </div>
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

function ConversationsCard({ k }: { k: LeadKpis }) {
  const talk = k.talk_listen_agent_pct
  return (
    <section aria-label="Conversation totals" className="rounded-xl border bg-surface p-5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="num text-2xl font-semibold">{k.conversations.toLocaleString()}</span>
        <span className="text-muted-foreground">Conversations</span>
        <span className="num rounded-full bg-positive-soft px-2.5 py-0.5 text-xs font-medium text-positive">
          {formatHoursMins(k.audio_seconds)}
        </span>
      </div>
      <dl className="mt-4 grid grid-cols-3 gap-3">
        <SubStat label="Detailed" value={k.detailed_pct == null ? '—' : `${Math.round(k.detailed_pct)}%`} />
        <SubStat label="Talk-to-Listen" value={talk == null ? '—' : `${talk}:${100 - talk}`} />
        <SubStat label="Quality Score" value={k.quality_pct == null ? '—' : `${Math.round(k.quality_pct)}%`} />
      </dl>
    </section>
  )
}

function SubStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="num text-base font-semibold">{value}</dd>
    </div>
  )
}

function LeadSummary({ k }: { k: LeadKpis }) {
  const pct = (n: number) => (k.total_leads ? Math.round((100 * n) / k.total_leads) : 0)
  const showDelta = k.has_previous_period
  const d = k.deltas
  return (
    <section aria-label="Lead summary" className="rounded-xl border bg-surface p-5">
      <dl className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Summary label="Total Leads" value={k.total_leads} delta={showDelta ? (d.total_leads ?? null) : undefined} />
        <Summary
          label="Unique Connected Leads"
          value={k.connected_leads}
          delta={showDelta ? (d.connected_leads ?? null) : undefined}
        />
        <Summary
          label="Not Connected Leads"
          value={k.not_connected_leads}
          delta={showDelta ? (d.not_connected_leads ?? null) : undefined}
          goodWhenDown
        />
      </dl>
      <dl className="mt-4 grid grid-cols-1 gap-4 border-t pt-4 sm:grid-cols-3">
        <Summary label="Won" value={k.won} pct={pct(k.won)} delta={showDelta ? (d.won ?? null) : undefined} />
        <Summary
          label="Lost"
          value={k.lost}
          pct={pct(k.lost)}
          delta={showDelta ? (d.lost ?? null) : undefined}
          goodWhenDown
        />
        <Summary
          label="In Progress"
          value={k.in_progress}
          pct={pct(k.in_progress)}
          delta={showDelta ? (d.in_progress ?? null) : undefined}
        />
      </dl>
    </section>
  )
}

interface SummaryProps {
  label: string
  value: number
  pct?: number
  /** undefined = no previous period, so no delta at all; null = previous period had no data. */
  delta?: number | null
  goodWhenDown?: boolean
}

function Summary({ label, value, pct, delta, goodWhenDown }: SummaryProps) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 flex flex-wrap items-baseline gap-x-2">
        <span className="num text-xl font-semibold">{value.toLocaleString()}</span>
        {pct !== undefined && <span className="num text-sm text-muted-foreground">({pct}%)</span>}
        {delta !== undefined && <Delta value={delta} goodWhenDown={goodWhenDown} />}
      </dd>
    </div>
  )
}

/** "↗ 12%" in green or "↘ 4%" in red against the previous period; "N/A —" when there's nothing to compare. */
function Delta({ value, goodWhenDown = false }: { value: number | null; goodWhenDown?: boolean }) {
  if (value == null) return <span className="text-xs text-muted-foreground">N/A —</span>
  const up = value >= 0
  const good = up !== goodWhenDown
  const Icon = up ? ArrowUpRight : ArrowDownRight
  return (
    <span className={cn('num inline-flex items-center text-xs font-medium', good ? 'text-positive' : 'text-negative')}>
      <Icon className="size-3.5" aria-hidden />
      <span className="sr-only">{up ? 'up' : 'down'} </span>
      {Math.abs(value)}%
    </span>
  )
}

function KpiSkeleton() {
  return (
    <div className="mb-6 space-y-4" aria-busy="true">
      <div className="grid gap-4 lg:grid-cols-[1fr_minmax(0,26rem)]">
        <Skeleton className="h-40 rounded-xl" />
        <Skeleton className="h-40 rounded-xl" />
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {BUCKETS.map((b) => (
          <Skeleton key={b} className="h-20 rounded-xl" />
        ))}
      </div>
    </div>
  )
}
