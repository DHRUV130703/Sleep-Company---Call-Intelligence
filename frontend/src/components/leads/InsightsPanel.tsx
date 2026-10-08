import { ArrowDownRight, ArrowRight, ArrowUpRight, Sparkles } from 'lucide-react'
import type { ReactNode } from 'react'
import { EmptyState } from '@/components/EmptyState'
import { humanize } from '@/lib/format'
import { INTENT_LABELS, INTENT_STYLES, MOOD_EMOJI } from '@/lib/labels'
import type { Bant, BantStatus, CustomerDetails, IntentInsight, LeadInsights, Mood } from '@/lib/types-leads'
import { cn } from '@/lib/utils'
import { ObjectionCard } from './ObjectionCard'

/** Left column of the Insights tab (PRD §6.4): intent, objections, BANT, mood, key details. */
export function InsightsPanel({ insights }: { insights: LeadInsights }) {
  const { intent, bant, mood, customer, objections, unanswered_questions } = insights
  if (!intent && objections.length === 0) {
    return (
      <EmptyState
        icon={Sparkles}
        title="No insights yet"
        description="Insights appear once at least one conversation for this lead has been analysed."
      />
    )
  }
  return (
    <div className="space-y-4">
      {intent && <IntentCard intent={intent} />}

      <Section title="Objections" count={objections.length}>
        {objections.length === 0 ? (
          <p className="text-muted-foreground">No objections raised.</p>
        ) : (
          <ul className="space-y-3">
            {objections.map((o, i) => (
              <li key={`${o.call_id}-${i}`}>
                <ObjectionCard objection={o} />
              </li>
            ))}
          </ul>
        )}
      </Section>

      {bant && <BantTiles bant={bant} />}
      {mood && <MoodCard mood={mood} />}
      {customer && <KeyDetails customer={customer} unanswered={unanswered_questions} />}
    </div>
  )
}

function Section({ title, count, children }: { title: string; count?: number; children: ReactNode }) {
  return (
    <section className="rounded-xl border bg-surface p-5">
      <h3 className="mb-3 font-semibold">
        {title}
        {count !== undefined && <span className="num ml-1.5 font-normal text-muted-foreground">({count})</span>}
      </h3>
      {children}
    </section>
  )
}

function IntentCard({ intent }: { intent: IntentInsight }) {
  return (
    <section className="rounded-xl border bg-surface p-5">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-semibold">Buying Intent</h3>
        <div className="flex items-center gap-2">
          <span className={cn('rounded-full px-2.5 py-0.5 text-sm font-semibold', INTENT_STYLES[intent.bucket])}>
            {INTENT_LABELS[intent.bucket] ?? humanize(intent.bucket)}
          </span>
          <span className="num rounded-full border px-2 py-0.5 text-sm font-semibold">{intent.score}/100</span>
        </div>
      </div>
      <ul className="space-y-1.5">
        {intent.positive_factors.map((f) => (
          <li key={`+${f}`} className="flex gap-2">
            <ArrowUpRight className="mt-0.5 size-4 shrink-0 text-positive" aria-label="Positive" />
            <span>{f}</span>
          </li>
        ))}
        {intent.negative_factors.map((f) => (
          <li key={`-${f}`} className="flex gap-2">
            <ArrowDownRight className="mt-0.5 size-4 shrink-0 text-negative" aria-label="Negative" />
            <span>{f}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}

const BANT_KEYS: (keyof Bant)[] = ['budget', 'authority', 'need', 'timeline']

const BANT_DOT: Record<BantStatus, { cls: string; label: string }> = {
  known: { cls: 'bg-positive', label: 'Known' },
  partial: { cls: 'bg-warning', label: 'Partial' },
  unknown: { cls: 'bg-muted-foreground/40', label: 'Unknown' },
}

function BantTiles({ bant }: { bant: Bant }) {
  return (
    <Section title="BANT">
      <ul className="grid gap-3 sm:grid-cols-2">
        {BANT_KEYS.map((key) => {
          const item = bant[key]
          const dot = BANT_DOT[item.status] ?? BANT_DOT.unknown
          return (
            <li key={key} className="rounded-lg border p-3">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium">{humanize(key)}</span>
                <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
                  <span className={cn('size-2 rounded-full', dot.cls)} aria-hidden />
                  {dot.label}
                </span>
              </div>
              <p className={cn('mt-1', !item.value && 'text-muted-foreground')}>{item.value || 'Unknown'}</p>
              {item.evidence && item.verified && (
                <blockquote className="mt-2 border-l-2 pl-2 text-xs text-muted-foreground italic">
                  “{item.evidence}”
                </blockquote>
              )}
            </li>
          )
        })}
      </ul>
    </Section>
  )
}

function MoodCard({ mood }: { mood: Mood }) {
  return (
    <Section title="Customer mood">
      <div className="flex flex-wrap items-center gap-3">
        <MoodValue label="Start" value={mood.start} />
        <ArrowRight className="size-4 text-muted-foreground" aria-hidden />
        <MoodValue label="End" value={mood.end} />
        {mood.trajectory && (
          <span className="rounded-full bg-surface-sunken px-2.5 py-0.5 text-xs">{humanize(mood.trajectory)}</span>
        )}
      </div>
    </Section>
  )
}

function MoodValue({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span aria-hidden>{MOOD_EMOJI[value] ?? ''}</span>
      <span className="font-medium">{humanize(value || 'unknown')}</span>
    </span>
  )
}

function KeyDetails({ customer, unanswered }: { customer: CustomerDetails; unanswered: string[] }) {
  const list = (items: string[]) => (items.length ? items.join(', ') : '')
  const rows: [string, string][] = [
    ['Products discussed', list(customer.products_discussed)],
    ['Size', customer.size],
    ['Budget', customer.budget],
    ['City', customer.city],
    ['Pincode', customer.pincode],
    ['Pain points', list(customer.pain_points)],
    ['Competitors mentioned', list(customer.competitors_mentioned)],
    ['Unanswered questions', list(unanswered)],
  ]
  return (
    <Section title="Key details captured">
      <dl className="grid grid-cols-[minmax(0,10rem)_1fr] gap-x-4 gap-y-2">
        {rows.map(([label, value]) => (
          <div key={label} className="contents">
            <dt className="text-muted-foreground">{label}</dt>
            <dd className={cn('min-w-0 break-words', !value && 'text-muted-foreground')}>{value || '—'}</dd>
          </div>
        ))}
      </dl>
    </Section>
  )
}
