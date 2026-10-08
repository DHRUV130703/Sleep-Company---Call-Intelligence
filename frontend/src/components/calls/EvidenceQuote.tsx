// A verbatim quote from the call. Verified quotes (found in the transcript) are clickable and jump
// the player there; unverified ones are greyed out and tagged, never presented as evidence (CLAUDE.md rule 6).

import { formatClock } from '@/lib/format'
import { cn } from '@/lib/utils'

interface Props {
  quote: string
  t: number
  verified: boolean
  onSeek: (seconds: number) => void
  className?: string
}

export function EvidenceQuote({ quote, t, verified, onSeek, className }: Props) {
  if (!quote) return null

  if (!verified) {
    return (
      <p className={cn('text-sm text-muted-foreground/70 italic', className)}>
        “{quote}”{' '}
        <span className="ml-1 rounded-full bg-surface-sunken px-1.5 py-0.5 text-[11px] not-italic text-muted-foreground">
          unverified
        </span>
      </p>
    )
  }

  const canSeek = t >= 0
  return (
    <button
      type="button"
      disabled={!canSeek}
      onClick={() => onSeek(t)}
      aria-label={canSeek ? `Play from ${formatClock(t)}: ${quote}` : undefined}
      className={cn(
        'block w-full rounded-lg border-l-2 border-border bg-surface-sunken px-3 py-1.5 text-left text-sm outline-none',
        'enabled:hover:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-default',
        className,
      )}
    >
      “{quote}”
      {canSeek && <span className="num ml-2 font-mono text-xs text-muted-foreground">▶ {formatClock(t)}</span>}
    </button>
  )
}
