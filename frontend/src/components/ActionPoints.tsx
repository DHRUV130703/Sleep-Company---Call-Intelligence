import { cn } from '@/lib/utils'

/** The short points under a next action. Older analyses have one "why" sentence instead of points. */
export function ActionPoints({ points, why, className }: { points?: string[]; why?: string; className?: string }) {
  const items = points?.length ? points : why ? [why] : []
  if (items.length === 0) return null
  return (
    <ul className={cn('space-y-1 text-muted-foreground', className)}>
      {items.map((p, i) => (
        <li key={i} className="flex gap-2">
          <span className="mt-[0.6em] size-1 shrink-0 rounded-full bg-current" aria-hidden />
          {p}
        </li>
      ))}
    </ul>
  )
}
