import type { Side } from '@/lib/types-compare'
import { cn } from '@/lib/utils'
import { formatValue } from './format-value'

interface Props {
  value: number | null
  /** The value that fills the whole bar (e.g. the larger of AI and Human in that row, or 100 for %). */
  max: number
  side: Side
  suffix?: string
}

/** A number followed by a thin bar in the side's colour. Used in tables (measured metrics, outcomes). */
export function ValueBar({ value, max, side, suffix = '' }: Props) {
  const pct = value && max > 0 ? Math.min(100, (value / max) * 100) : 0
  return (
    <div className="flex min-w-24 items-center gap-2">
      <span className="num w-12 shrink-0 text-right">{formatValue(value, suffix)}</span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-surface-sunken" aria-hidden>
        <div
          className={cn('h-full rounded-full transition-[width] duration-200 ease-out motion-reduce:transition-none', side === 'ai' ? 'bg-ai' : 'bg-human')}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}
