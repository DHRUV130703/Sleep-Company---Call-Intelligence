import { CalendarClock, Route } from 'lucide-react'
import { formatShortDate } from '@/lib/leads-format'
import type { PathToConversion as Path } from '@/lib/types-leads'
import { cn } from '@/lib/utils'

/**
 * Right panel of the Insights tab (PRD §6.4): what happened so far and what to do next.
 * With several calls the summary is cumulative across all of them (latest weighted highest).
 */
export function PathToConversion({ path, className }: { path: Path | null; className?: string }) {
  return (
    <aside
      aria-labelledby="path-title"
      className={cn('rounded-xl border bg-surface p-5 lg:sticky lg:top-20 lg:max-h-[calc(100dvh-6rem)] lg:overflow-y-auto', className)}
    >
      <h3 id="path-title" className="flex items-center gap-2 font-semibold">
        <Route className="size-4 text-ai" aria-hidden />
        Path to Conversion
      </h3>

      {!path ? (
        <p className="mt-3 text-muted-foreground">Next steps appear once a conversation has been analysed.</p>
      ) : (
        <>
          <section className="mt-4">
            <h4 className="text-sm font-medium">Previous Conversation Summary</h4>
            {path.based_on_calls > 1 && (
              <p className="num text-xs text-muted-foreground">Across all {path.based_on_calls} conversations</p>
            )}
            <ul className="mt-2 list-disc space-y-1 pl-5">
              {path.bullets.map((b) => (
                <li key={b}>{b}</li>
              ))}
            </ul>
          </section>

          <section className="mt-5 border-t pt-4">
            <h4 className="text-sm font-medium">What to do next?</h4>
            {path.next_actions.length === 0 ? (
              <p className="mt-2 text-muted-foreground">No follow-up needed.</p>
            ) : (
              <ol className="mt-2 space-y-4">
                {path.next_actions.map((a, i) => (
                  <li key={`${i}-${a.title}`} className="flex gap-3">
                    <span className="num grid size-6 shrink-0 place-items-center rounded-full bg-ai-soft text-xs font-semibold text-ai">
                      {i + 1}
                    </span>
                    <div className="min-w-0 space-y-1">
                      <p className="font-semibold">{a.title}</p>
                      {a.say && (
                        <p className="rounded-md bg-surface-sunken px-2.5 py-1.5">
                          <span aria-hidden>👉 </span>
                          <span className="font-semibold">Say:</span> {a.say}
                        </p>
                      )}
                      {a.why && <p className="text-muted-foreground">{a.why}</p>}
                      {(a.due || a.when) && (
                        <p className="inline-flex items-center gap-1 text-xs text-warning">
                          <CalendarClock className="size-3.5" aria-hidden />
                          Due {a.due ? formatShortDate(a.due) : ''}
                          {a.when && ` (${a.when})`}
                        </p>
                      )}
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </section>
        </>
      )}
    </aside>
  )
}
