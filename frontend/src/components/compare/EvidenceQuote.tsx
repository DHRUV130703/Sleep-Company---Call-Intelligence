import { Link } from 'react-router'
import { formatClock } from '@/lib/format'
import type { Side } from '@/lib/types-compare'
import { cn } from '@/lib/utils'

interface Props {
  callId: number
  label: string
  quote: string
  /** Seconds into the call where the quote starts. */
  t: number
  side?: Side
}

/** A short verbatim quote that opens the call's transcript at that moment. */
export function EvidenceQuote({ callId, label, quote, t, side }: Props) {
  const seconds = Math.max(0, Math.floor(t))
  return (
    <Link
      to={`/calls/${callId}?t=${seconds}`}
      className={cn(
        'block rounded-md border-l-2 bg-surface-sunken px-2.5 py-1.5 text-[13px] hover:bg-accent focus-visible:outline-2 focus-visible:outline-ring',
        side === 'ai' ? 'border-ai' : side === 'human' ? 'border-human' : 'border-border',
      )}
      aria-label={`Open ${label} at ${formatClock(seconds)}: “${quote}”`}
    >
      <span className="italic">“{quote}”</span>
      <span className="mt-0.5 block font-mono text-xs text-muted-foreground">
        {label} · {formatClock(seconds)}
      </span>
    </Link>
  )
}
