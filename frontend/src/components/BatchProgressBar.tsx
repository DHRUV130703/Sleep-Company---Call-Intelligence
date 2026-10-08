import type { BatchCounts } from '@/lib/types-batches'
import { cn } from '@/lib/utils'

/** Stacked bar: done (green) · not connected (grey) · failed (red) · in progress (blue) · queued (track). */
export function BatchProgressBar({ counts, className }: { counts: BatchCounts; className?: string }) {
  const total = counts.total || 1
  const parts = [
    { n: counts.done, cls: 'bg-positive', label: 'done' },
    { n: counts.skipped, cls: 'bg-muted-foreground/40', label: 'not connected' },
    { n: counts.failed, cls: 'bg-negative', label: 'failed' },
    { n: counts.running, cls: 'bg-ai animate-pulse', label: 'in progress' },
  ]
  const finished = counts.done + counts.skipped + counts.failed
  return (
    <div
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={counts.total}
      aria-valuenow={finished}
      aria-label={`${finished} of ${counts.total} calls finished`}
      className={cn('flex h-2 overflow-hidden rounded-full bg-surface-sunken', className)}
    >
      {parts.map((p) =>
        p.n ? (
          <div
            key={p.label}
            className={cn('h-full transition-[width] duration-300', p.cls)}
            style={{ width: `${(100 * p.n) / total}%` }}
          />
        ) : null,
      )}
    </div>
  )
}
