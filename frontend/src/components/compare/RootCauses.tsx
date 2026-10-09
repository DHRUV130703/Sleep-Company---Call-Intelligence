import { useState } from 'react'
import type { CompareResult, RootCause } from '@/lib/types-compare'
import { CompareSection } from './CompareSection'
import { AreaChip, BetterLine, Moment, PriorityPill, ToggleRow } from './ImprovementBits'

/** Root causes: repeated bot failure patterns, who owns the fix, and every bot call where it happened. */
export function RootCauses({ data }: { data: CompareResult }) {
  const causes = data.improvement.root_causes
  const [open, setOpen] = useState<string | null>(causes[0]?.pattern ?? null)
  return (
    <CompareSection
      id="root-causes"
      title="Root causes — repeated bot failures"
      caption="Repeated bot failures. Open one to see every call where it happened."
    >
      {data.scores.ai.n === 0 ? (
        <p className="text-muted-foreground">No analysed bot calls in this selection.</p>
      ) : causes.length === 0 ? (
        <p className="text-muted-foreground">No failure patterns found in the bot calls.</p>
      ) : (
        <ol className="divide-y rounded-lg border">
          {causes.map((c) => (
            <CauseRow
              key={c.pattern}
              cause={c}
              open={open === c.pattern}
              onToggle={() => setOpen(open === c.pattern ? null : c.pattern)}
            />
          ))}
        </ol>
      )}
    </CompareSection>
  )
}

function CauseRow({ cause, open, onToggle }: { cause: RootCause; open: boolean; onToggle: () => void }) {
  const id = `cause-${cause.pattern}`
  return (
    <li>
      <ToggleRow open={open} onToggle={onToggle} controls={id}>
        <div className="grid gap-2 md:grid-cols-[6rem_minmax(0,1fr)_12rem] md:items-center md:gap-4">
          <PriorityPill priority={cause.priority} />
          <div className="min-w-0">
            <div className="font-semibold">{cause.label}</div>
            <AreaChip area={cause.area} />
          </div>
          <div>
            <div className="num text-[13px] font-medium">
              {cause.count} of {cause.of} bot {cause.of === 1 ? 'call' : 'calls'} ({cause.share}%)
            </div>
            <div className="mt-1 h-2 overflow-hidden rounded-full bg-surface-sunken" aria-hidden>
              <div className="h-full rounded-full bg-ai" style={{ width: `${cause.share}%` }} />
            </div>
          </div>
        </div>
      </ToggleRow>
      {open && (
        <div id={id} className="space-y-4 border-t bg-surface px-3 py-4">
          {cause.fix && <BetterLine label="How to fix" text={cause.fix} />}
          <ul className="grid gap-4 md:grid-cols-2">
            {cause.calls.map((hit, i) => (
              <li key={`${hit.call_id}-${i}`} className="rounded-lg border bg-card p-3">
                <Moment
                  refTo={hit}
                  quote={hit.quote}
                  t={hit.t}
                  side="ai"
                  note={hit.description}
                  better={hit.better}
                />
              </li>
            ))}
          </ul>
        </div>
      )}
    </li>
  )
}
