// Small shared pieces of the bot improvement plan: priority pill, owner-area chip, "better" line,
// links to the call (at the moment) and its lead, a bot moment card and a show/hide toggle.

import { ChevronDown, Lightbulb, UserRound } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { formatClock } from '@/lib/format'
import type { CallRef, ImprovementPriority, Side } from '@/lib/types-compare'
import { cn } from '@/lib/utils'
import { EvidenceQuote } from './EvidenceQuote'

const PRIORITY: Record<ImprovementPriority, { text: string; style: string }> = {
  high: { text: 'Fix first', style: 'bg-negative-soft text-negative' },
  medium: { text: 'Fix next', style: 'bg-warning-soft text-warning' },
  low: { text: 'Minor', style: 'bg-surface-sunken text-muted-foreground' },
  none: { text: 'OK', style: 'bg-positive-soft text-positive' },
}

export function PriorityPill({ priority, className }: { priority: ImprovementPriority; className?: string }) {
  const p = PRIORITY[priority]
  return (
    <span className={cn('inline-block w-fit shrink-0 rounded-full px-2 py-0.5 text-xs font-medium', p.style, className)}>
      {p.text}
      <span className="sr-only"> (priority: {priority})</span>
    </span>
  )
}

/** Which part of the bot owns the fix (Script, Knowledge base…). */
export function AreaChip({ area }: { area: string }) {
  if (!area) return null
  return (
    <span className="inline-block w-fit rounded-md border bg-surface px-1.5 py-0.5 text-xs text-muted-foreground">
      {area}
    </span>
  )
}

/** What the bot should have said or done instead. */
export function BetterLine({ text, label = 'Better' }: { text: string; label?: string }) {
  if (!text) return null
  return (
    <p className="flex items-start gap-1.5 rounded-md bg-positive-soft px-2.5 py-1.5 text-[13px]">
      <Lightbulb className="mt-0.5 size-3.5 shrink-0 text-positive" aria-hidden />
      <span>
        <span className="font-medium text-positive">{label}: </span>
        {text}
      </span>
    </p>
  )
}

/** "Open call at 1:23 · Lead" links for one example. */
export function CallLinks({ refTo, t }: { refTo: CallRef; t?: number }) {
  const seconds = t !== undefined && t >= 0 ? Math.floor(t) : undefined
  return (
    <span className="inline-flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
      <Link
        to={`/calls/${refTo.call_id}${seconds !== undefined ? `?t=${seconds}` : ''}`}
        className="font-mono font-medium underline-offset-4 hover:underline focus-visible:underline"
      >
        {refTo.label}
        {seconds !== undefined && <span className="text-muted-foreground"> · {formatClock(seconds)}</span>}
      </Link>
      {refTo.lead_id !== null && (
        <Link
          to={`/leads/${refTo.lead_id}`}
          className="inline-flex items-center gap-1 text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
        >
          <UserRound className="size-3" aria-hidden />
          Lead
        </Link>
      )}
    </span>
  )
}

interface MomentProps {
  refTo: CallRef
  quote: string
  t: number
  side: Side
  /** Why this moment matters (the review's reason, the failure's description…). */
  note?: ReactNode
  better?: string
}

/** One moment from a call: the verified quote (opens the call there), a note, and the better line. */
export function Moment({ refTo, quote, t, side, note, better }: MomentProps) {
  return (
    <div className="space-y-1.5">
      {quote ? (
        <EvidenceQuote callId={refTo.call_id} label={refTo.label} quote={quote} t={t} side={side} />
      ) : (
        <CallLinks refTo={refTo} t={t} />
      )}
      {note && <p className="text-[13px] text-muted-foreground">{note}</p>}
      {quote && refTo.lead_id !== null && (
        <Link
          to={`/leads/${refTo.lead_id}`}
          className="inline-flex items-center gap-1 text-xs text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
        >
          <UserRound className="size-3" aria-hidden />
          Open lead
        </Link>
      )}
      {better && <BetterLine text={better} />}
    </div>
  )
}

/** A full-width row button that shows/hides its details. */
export function ToggleRow({
  open,
  onToggle,
  controls,
  children,
}: {
  open: boolean
  onToggle: () => void
  controls: string
  children: ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={open}
      aria-controls={controls}
      className="flex w-full items-start gap-3 px-3 py-3 text-left hover:bg-accent/50 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring"
    >
      <div className="min-w-0 flex-1">{children}</div>
      <ChevronDown
        className={cn('mt-0.5 size-4 shrink-0 text-muted-foreground transition-transform', open && 'rotate-180')}
        aria-hidden
      />
    </button>
  )
}
