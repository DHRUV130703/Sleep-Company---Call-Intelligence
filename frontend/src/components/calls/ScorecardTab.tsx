// The call's scorecard: one row per dimension from config/scorecard.yaml (1 = poor … 5 = excellent).

import { humanize } from '@/lib/format'
import type { CallAnalysis } from '@/lib/types-calls'
import { cn } from '@/lib/utils'
import { EvidenceQuote } from './EvidenceQuote'

function scoreColor(score: number): string {
  if (score >= 4) return 'bg-positive'
  if (score === 3) return 'bg-warning'
  return 'bg-negative'
}

export function ScorecardTab({ analysis, onSeek }: { analysis: CallAnalysis; onSeek: (t: number) => void }) {
  if (analysis.scorecard.length === 0) {
    return <p className="text-muted-foreground">No scorecard for this call.</p>
  }
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-x-6 gap-y-1">
        {analysis.review_score != null && (
          <div>
            <span className="text-muted-foreground">Review score </span>
            <span className="num font-semibold">{analysis.review_score.toFixed(1)} / 5</span>
          </div>
        )}
        {analysis.quality_pct != null && (
          <div>
            <span className="text-muted-foreground">Quality </span>
            <span className="num font-semibold">{Math.round(analysis.quality_pct)}%</span>
          </div>
        )}
      </div>

      <ol className="divide-y">
        {analysis.scorecard.map((item) => (
          <li key={item.key} className="space-y-1.5 py-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-medium">{humanize(item.key)}</span>
              <ScoreBars score={item.score} />
            </div>
            {item.reason && <p className="text-muted-foreground">{item.reason}</p>}
            <EvidenceQuote quote={item.evidence} t={item.t} verified={item.verified} onSeek={onSeek} />
          </li>
        ))}
      </ol>
    </div>
  )
}

/** Five small bars, `score` of them filled, plus the number (colour is never the only signal). */
function ScoreBars({ score }: { score: number }) {
  return (
    <span className="inline-flex items-center gap-2" aria-label={`${score} out of 5`}>
      <span className="flex gap-0.5" aria-hidden>
        {[1, 2, 3, 4, 5].map((n) => (
          <span key={n} className={cn('h-2.5 w-4 rounded-sm', n <= score ? scoreColor(score) : 'bg-surface-sunken')} />
        ))}
      </span>
      <span className="num w-7 text-right text-xs font-medium" aria-hidden>
        {score}/5
      </span>
    </span>
  )
}
