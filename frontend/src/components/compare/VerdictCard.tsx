import { Info } from 'lucide-react'
import type { CompareResult, Side } from '@/lib/types-compare'
import { cn } from '@/lib/utils'
import { CompareSection, SideLabel } from './CompareSection'

/** B. One-line verdict written by the AI, next to the two average review scores (computed in code). */
export function VerdictCard({ data }: { data: CompareResult }) {
  return (
    <CompareSection
      id="verdict"
      title="Verdict"
      caption="The headline is written by the AI from the numbers below. The scores are averages of each call's review."
    >
      <div className="grid gap-6 lg:grid-cols-[1fr_auto] lg:items-center">
        {data.synthesis ? (
          <p className="text-lg leading-snug font-medium text-balance md:text-xl">{data.synthesis.verdict_headline}</p>
        ) : (
          <p className="flex items-start gap-2 text-muted-foreground">
            <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
            {data.synthesis_error ?? 'The written summary is not available for this selection.'}
          </p>
        )}
        <div className="grid grid-cols-2 gap-3 sm:gap-4">
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
    </div>
  )
}
