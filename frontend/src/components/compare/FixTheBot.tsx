import { Info } from 'lucide-react'
import { humanize } from '@/lib/format'
import type { CompareResult, Priority, RecommendedChange, Side } from '@/lib/types-compare'
import { cn } from '@/lib/utils'
import { CompareSection } from './CompareSection'
import { AreaChip, BetterLine, CallLinks } from './ImprovementBits'

const PRIORITY_ORDER: Record<Priority, number> = { high: 0, medium: 1, low: 2 }
const PRIORITY_STYLE: Record<Priority, string> = {
  high: 'bg-negative-soft text-negative',
  medium: 'bg-warning-soft text-warning',
  low: 'bg-surface-sunken text-muted-foreground',
}

/** What to change in the bot (AI-written): concrete changes with the new line and example calls, then strengths per side. */
export function FixTheBot({ data }: { data: CompareResult }) {
  const s = data.synthesis
  const changes = s ? [...s.recommended_changes].sort((a, b) => PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority]) : []

  return (
    <CompareSection
      id="fix"
      title="Recommended changes to the bot"
      caption="Written by the AI from these calls, most impactful first."
    >
      <div className="space-y-6">
        {s &&
          (changes.length === 0 ? (
            <p className="text-muted-foreground">No changes recommended.</p>
          ) : (
            <ol className="divide-y rounded-lg border">
              {changes.map((c, i) => (
                <ChangeRow key={i} change={c} />
              ))}
            </ol>
          ))}
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
            {data.synthesis_error ?? 'The written part is not available for this selection.'} The improvement
            plan, root causes and call-by-call RCA are computed in code and are complete.
          </p>
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
      <div className="min-w-0 flex-1 space-y-1.5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-semibold">{change.change}</span>
          <AreaChip area={change.area} />
        </div>
        <p className="text-muted-foreground">{change.rationale}</p>
        <BetterLine label="New bot line" text={change.bot_line} />
        {change.examples.length > 0 && (
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
            <span className="text-xs text-muted-foreground">Seen in:</span>
            {change.examples.map((e) => (
              <CallLinks key={e.call_id} refTo={e} />
            ))}
          </div>
        )}
      </div>
    </li>
  )
}
