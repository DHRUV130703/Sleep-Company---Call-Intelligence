import { INTENT_LABELS, INTENT_STYLES } from '@/lib/labels'
import { cn } from '@/lib/utils'

/** "High Intent 81/100" pill. Shows "—" when there is no intent yet. */
export function IntentPill({ bucket, score, short = false }: { bucket?: string | null; score?: number | null; short?: boolean }) {
  if (!bucket) return <span className="text-muted-foreground">—</span>
  const label = INTENT_LABELS[bucket] ?? bucket
  return (
    <span className={cn('inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium', INTENT_STYLES[bucket])}>
      {short ? label.replace(' Intent', '') : label}
      {score != null && <span className="num opacity-80">{score}/100</span>}
    </span>
  )
}
