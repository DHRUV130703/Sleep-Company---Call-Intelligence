import { CircleCheck, CircleX, Loader2, MinusCircle, Clock } from 'lucide-react'
import { STAGE_LABELS } from '@/lib/labels'
import { cn } from '@/lib/utils'

/** Where a call is in the pipeline: Queued · Transcribing… · Done · Failed · Skipped. */
export function CallStatusPill({ stage, status }: { stage: string; status: string }) {
  const map = {
    done: { icon: CircleCheck, cls: 'text-positive bg-positive-soft', text: 'Done' },
    failed: { icon: CircleX, cls: 'text-negative bg-negative-soft', text: 'Failed' },
    skipped: { icon: MinusCircle, cls: 'text-muted-foreground bg-surface-sunken', text: 'Not connected' },
    running: { icon: Loader2, cls: 'text-ai bg-ai-soft', text: STAGE_LABELS[stage] ?? stage },
    queued: { icon: Clock, cls: 'text-muted-foreground bg-surface-sunken', text: stage === 'queued' ? 'Queued' : `Waiting · ${STAGE_LABELS[stage] ?? stage}` },
  } as const
  const m = map[status as keyof typeof map] ?? map.queued
  const Icon = m.icon
  return (
    <span className={cn('inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium', m.cls)}>
      <Icon className={cn('size-3.5', status === 'running' && 'animate-spin')} aria-hidden />
      {m.text}
    </span>
  )
}
