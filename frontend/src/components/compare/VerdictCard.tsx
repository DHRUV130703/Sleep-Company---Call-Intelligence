import { Info, TrendingDown, TrendingUp, Equal } from 'lucide-react'
import type { CompareResult, Side, Verdict } from '@/lib/types-compare'
import { cn } from '@/lib/utils'
import { CompareSection, SideLabel } from './CompareSection'

const STATUS_STYLE: Record<Verdict['status'], string> = {
  behind: 'bg-negative-soft text-negative',
  on_par: 'bg-warning-soft text-warning',
  ahead: 'bg-positive-soft text-positive',
  no_benchmark: 'bg-surface-sunken text-muted-foreground',
  no_data: 'bg-surface-sunken text-muted-foreground',
}
const STATUS_ICON = { behind: TrendingDown, on_par: Equal, ahead: TrendingUp, no_benchmark: Info, no_data: Info }

/** B. Is the bot behind, on par or ahead of humans? Status and points computed in code, headline by the AI. */
export function VerdictCard({ data }: { data: CompareResult }) {
  const v = data.improvement.verdict
  const s = data.synthesis
  const Icon = STATUS_ICON[v.status]
  return (
    <CompareSection
      id="verdict"
      title="Verdict"
      caption="Status, readiness and key points are computed from the call reviews. The headline and assessment are written by the AI."
    >
      <div className="grid gap-6 lg:grid-cols-[1fr_auto]">
        <div className="min-w-0 space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <span className={cn('inline-flex items-center gap-1.5 rounded-full px-3 py-1 font-medium', STATUS_STYLE[v.status])}>
              <Icon className="size-4" aria-hidden />
              {v.label}
            </span>
            {v.readiness_pct !== null && (
              <span className="num text-muted-foreground">
                Bot reaches <span className="font-semibold text-foreground">{v.readiness_pct}%</span> of human quality
              </span>
            )}
          </div>

          {s ? (
            <div className="space-y-1.5">
              <p className="text-lg leading-snug font-medium text-balance md:text-xl">{s.verdict_headline}</p>
              {s.verdict_detail && <p className="max-w-3xl text-muted-foreground">{s.verdict_detail}</p>}
            </div>
          ) : (
            <p className="flex items-start gap-2 text-muted-foreground">
              <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
              {data.synthesis_error ?? 'The written assessment is not available for this selection.'}
            </p>
          )}

          {v.points.length > 0 && (
            <ul className="list-disc space-y-1 pl-5">
              {v.points.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          )}

          {v.top_levers.length > 0 && (
            <p>
              <span className="font-medium">Fix first: </span>
              {v.top_levers.map((l, i) => (
                <span key={l}>
                  {i > 0 && ', '}
                  <a href="#plan" className="underline underline-offset-4 hover:text-foreground">
                    {l}
                  </a>
                </span>
              ))}
            </p>
          )}
        </div>

        <div className="grid h-fit grid-cols-2 gap-3 sm:gap-4">
          <BigScore side="ai" data={data} />
          <BigScore side="human" data={data} />
        </div>
      </div>
    </CompareSection>
  )
}

function BigScore({ side, data }: { side: Side; data: CompareResult }) {
  const s = data.scores[side]
  const score = s.avg_review === null ? '—' : s.avg_review.toFixed(1)
  const positive = data.improvement.verdict.positive_outcome_pct[side]
  return (
    <div className={cn('rounded-lg px-4 py-3 sm:min-w-44', side === 'ai' ? 'bg-ai-soft' : 'bg-human-soft')}>
      <SideLabel side={side} className="text-xs" />
      <div className="mt-1 flex items-baseline gap-1">
        <span className={cn('num text-[44px] leading-none font-semibold', side === 'ai' ? 'text-ai' : 'text-human')}>
          {score}
        </span>
        <span className="text-muted-foreground">/ 5</span>
      </div>
      <div className="num mt-1.5 text-xs text-muted-foreground">
        {s.n} of {s.of} {s.of === 1 ? 'call' : 'calls'} reviewed
      </div>
      {positive !== null && (
        <div className="num mt-0.5 text-xs text-muted-foreground">{positive}% end with a concrete next step</div>
      )}
    </div>
  )
}
