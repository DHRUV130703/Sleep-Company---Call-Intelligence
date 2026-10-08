import { Info } from 'lucide-react'
import { humanize } from '@/lib/format'
import type { CompareResult, Priority, RecommendedChange, Side } from '@/lib/types-compare'
import { cn } from '@/lib/utils'
import { CompareSection } from './CompareSection'
import { EvidenceQuote } from './EvidenceQuote'

const PRIORITY_ORDER: Record<Priority, number> = { high: 0, medium: 1, low: 2 }
const PRIORITY_STYLE: Record<Priority, string> = {
  high: 'bg-negative-soft text-negative',
  medium: 'bg-warning-soft text-warning',
  low: 'bg-surface-sunken text-muted-foreground',
}

/** G. What to change in the bot: strengths per side, outcomes, repeated failures, recommended changes. */
export function FixTheBot({ data }: { data: CompareResult }) {
  const s = data.synthesis
  const changes = s ? [...s.recommended_changes].sort((a, b) => PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority]) : []

  return (
    <CompareSection
      id="fix"
      title="What to fix in the bot"
      caption="Failure patterns are counted in code. Strengths, the outcomes paragraph and recommendations are written by the AI."
    >
      <div className="space-y-6">
        {s ? (
          <>
            <div className="grid gap-4 md:grid-cols-2">
              <BulletColumn side="ai" title="Where the AI does better" items={s.ai_better} />
              <BulletColumn side="human" title="Where humans do better" items={s.human_better} />
            </div>
            {s.outcomes_paragraph && (
              <div>
                <h4 className="mb-1 font-medium">Outcomes</h4>
                <p className="max-w-3xl">{s.outcomes_paragraph}</p>
              </div>
            )}
          </>
        ) : (
          <p className="flex items-start gap-2 text-muted-foreground">
            <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
            {data.synthesis_error ?? 'The written part is not available for this selection.'}
          </p>
        )}

        <FailurePatterns data={data} />

        {s && (
          <div>
            <h4 className="mb-2 font-medium">Recommended changes</h4>
            {changes.length === 0 ? (
              <p className="text-muted-foreground">No changes recommended.</p>
            ) : (
              <ol className="divide-y rounded-lg border">
                {changes.map((c, i) => (
                  <ChangeRow key={i} change={c} />
                ))}
              </ol>
            )}
          </div>
        )}
      </div>
    </CompareSection>
  )
}

function BulletColumn({ side, title, items }: { side: Side; title: string; items: string[] }) {
  return (
    <div className={cn('rounded-lg border-l-2 px-4 py-3', side === 'ai' ? 'border-ai bg-ai-soft' : 'border-human bg-human-soft')}>
      <h4 className={cn('mb-1.5 font-medium', side === 'ai' ? 'text-ai' : 'text-human')}>{title}</h4>
      {items.length === 0 ? (
        <p className="text-muted-foreground">Nothing stood out.</p>
      ) : (
        <ul className="list-disc space-y-1 pl-5">
          {items.map((t) => (
            <li key={t}>{t}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

function FailurePatterns({ data }: { data: CompareResult }) {
  const patterns = data.failure_patterns
  return (
    <div>
      <h4 className="mb-2 font-medium">Repeated AI failure patterns</h4>
      {data.scores.ai.n === 0 ? (
        <p className="text-muted-foreground">No analysed AI calls in this selection.</p>
      ) : patterns.length === 0 ? (
        <p className="text-muted-foreground">No failure patterns found in the AI calls.</p>
      ) : (
        <ul className="grid gap-3 md:grid-cols-2">
          {patterns.map((p) => (
            <li key={p.pattern} className="rounded-lg border p-3">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <span className="font-medium">{humanize(p.pattern)}</span>
                <span className="num text-xs text-muted-foreground">
                  {p.count} of {p.of} AI {p.of === 1 ? 'call' : 'calls'}
                </span>
              </div>
              {p.evidence.length > 0 && (
                <ul className="mt-2 space-y-1.5">
                  {p.evidence.map((ev, i) => (
                    <li key={`${ev.call_id}-${i}`}>
                      <EvidenceQuote callId={ev.call_id} label={ev.label} quote={ev.quote} t={ev.t} side="ai" />
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function ChangeRow({ change }: { change: RecommendedChange }) {
  return (
    <li className="flex flex-col gap-1.5 px-3 py-3 sm:flex-row sm:items-start sm:gap-3">
      <span
        className={cn(
          'w-fit shrink-0 rounded-full px-2 py-0.5 text-xs font-medium sm:w-16 sm:text-center',
          PRIORITY_STYLE[change.priority],
        )}
      >
        {humanize(change.priority)}
        <span className="sr-only"> priority</span>
      </span>
      <div className="min-w-0">
        <div className="font-semibold">{change.change}</div>
        <p className="mt-0.5 text-muted-foreground">{change.rationale}</p>
      </div>
    </li>
  )
}
