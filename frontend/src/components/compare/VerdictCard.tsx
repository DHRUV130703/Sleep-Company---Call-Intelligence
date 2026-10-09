import { Equal, Info, Loader2, TrendingDown, TrendingUp, TriangleAlert } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { formatHoursMins } from '@/lib/format'
import type { CompareResult, Side, Verdict } from '@/lib/types-compare'
import { cn } from '@/lib/utils'
import { SideLabel } from './CompareSection'

const STATUS_STYLE: Record<Verdict['status'], string> = {
  behind: 'bg-negative-soft text-negative',
  on_par: 'bg-warning-soft text-warning',
  ahead: 'bg-positive-soft text-positive',
  no_benchmark: 'bg-surface-sunken text-muted-foreground',
  no_data: 'bg-surface-sunken text-muted-foreground',
}
const STATUS_ICON = { behind: TrendingDown, on_par: Equal, ahead: TrendingUp, no_benchmark: Info, no_data: Info }

/** The page's one-glance answer: is the bot behind, by how much, what to fix first — and what it's based on. */
export function VerdictCard({ data }: { data: CompareResult }) {
  const v = data.improvement.verdict
  const s = data.synthesis
  const Icon = STATUS_ICON[v.status]
  return (
    <Card className="py-5">
      <CardContent className="space-y-5 px-5">
        <div className="grid gap-6 lg:grid-cols-[1fr_auto]">
          <div className="min-w-0 space-y-3">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
              <span className={cn('inline-flex items-center gap-1.5 rounded-full px-3 py-1 font-medium', STATUS_STYLE[v.status])}>
                <Icon className="size-4" aria-hidden />
                {v.label}
              </span>
              {v.readiness_pct !== null && (
                <span className="num text-muted-foreground">
                  <span className="font-semibold text-foreground">{v.readiness_pct}%</span> of human quality
                </span>
              )}
            </div>
            {s ? (
              <>
                <p className="text-lg leading-snug font-medium text-balance md:text-xl">{s.verdict_headline}</p>
                {s.verdict_detail && <p className="max-w-3xl text-muted-foreground">{s.verdict_detail}</p>}
              </>
            ) : (
              v.points[0] && <p className="text-lg leading-snug font-medium text-balance">{v.points[0]}</p>
            )}
            {v.top_levers.length > 0 && (
              <p>
                <span className="text-muted-foreground">Fix first: </span>
                <span className="font-medium">{v.top_levers.join(' · ')}</span>
              </p>
            )}
          </div>
          <div className="grid h-fit grid-cols-2 gap-3">
            <Score side="ai" data={data} />
            <Score side="human" data={data} />
          </div>
        </div>

        {v.points.length > 1 && (
          <ul className="grid gap-x-8 gap-y-1.5 border-t pt-4 text-[13px] text-muted-foreground md:grid-cols-2">
            {(s ? v.points : v.points.slice(1)).map((p) => (
              <li key={p} className="flex gap-2">
                <span aria-hidden>•</span>
                <span>{p}</span>
              </li>
            ))}
          </ul>
        )}

        <BasedOn data={data} />
      </CardContent>
    </Card>
  )
}

function Score({ side, data }: { side: Side; data: CompareResult }) {
  const score = data.scores[side].avg_review
  const positive = data.improvement.verdict.positive_outcome_pct[side]
  return (
    <div className={cn('rounded-lg px-4 py-3 sm:min-w-40', side === 'ai' ? 'bg-ai-soft' : 'bg-human-soft')}>
      <SideLabel side={side} className="text-xs" />
      <div className="mt-1 flex items-baseline gap-1">
        <span className={cn('num text-4xl leading-none font-semibold', side === 'ai' ? 'text-ai' : 'text-human')}>
          {score === null ? '—' : score.toFixed(1)}
        </span>
        <span className="text-muted-foreground">/ 5</span>
      </div>
      {positive !== null && (
        <div className="num mt-1.5 text-xs text-muted-foreground">{positive}% reach a next step</div>
      )}
    </div>
  )
}

/** One quiet line with the numbers behind the verdict, plus warnings only when they matter. */
function BasedOn({ data }: { data: CompareResult }) {
  const { ai, human } = data.records
  const failed = ai.failed + human.failed
  const notConnected = ai.not_connected + human.not_connected
  const inProgress = ai.in_progress + human.in_progress
  const audio = ai.audio_seconds + human.audio_seconds
  const parts = [
    `${ai.analysed} of ${ai.uploaded} bot calls and ${human.analysed} of ${human.uploaded} human calls analysed`,
    audio >= 60 ? `${formatHoursMins(audio)} of audio` : null,
    failed ? `${failed} failed` : null,
    notConnected ? `${notConnected} not connected` : null,
  ].filter(Boolean)
  return (
    <div className="space-y-2 border-t pt-3 text-xs text-muted-foreground">
      <p className="num">Based on {parts.join(' · ')}.</p>
      {data.sample_warning && (
        <p role="status" className="flex items-start gap-1.5 text-warning">
          <TriangleAlert className="mt-px size-3.5 shrink-0" aria-hidden />
          {data.sample_warning}
        </p>
      )}
      {inProgress > 0 && (
        <p role="status" className="flex items-center gap-1.5">
          <Loader2 className="size-3.5 animate-spin motion-reduce:animate-none" aria-hidden />
          {inProgress} {inProgress === 1 ? 'call is' : 'calls are'} still processing — re-run when done.
        </p>
      )}
    </div>
  )
}
