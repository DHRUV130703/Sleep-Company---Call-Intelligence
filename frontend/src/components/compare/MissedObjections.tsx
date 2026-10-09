import type { CompareResult } from '@/lib/types-compare'
import { CompareSection, SideLabel } from './CompareSection'
import { Moment } from './ImprovementBits'

/** Objections the bot did not handle well, per type, with the better response and a human example. */
export function MissedObjections({ data }: { data: CompareResult }) {
  const rows = data.improvement.objections
  if (data.scores.ai.n === 0) return null
  return (
    <CompareSection
      id="objections"
      title="Objections the bot missed"
      caption="What customers pushed back on, and what the bot should have said."
    >
      {rows.length === 0 ? (
        <p className="text-muted-foreground">The bot handled every objection in this selection well.</p>
      ) : (
        <div className="space-y-6">
          {rows.map((o) => (
            <div key={o.type}>
              <h4 className="mb-2 flex flex-wrap items-baseline gap-x-3 font-medium">
                {o.label}
                <span className="num text-xs font-normal text-muted-foreground">
                  {o.missed.length} of {o.total} not handled by the bot
                </span>
              </h4>
              <div className="grid gap-4 md:grid-cols-2">
                <ul className="space-y-3">
                  {o.missed.map((m, i) => (
                    <li key={`${m.call_id}-${i}`} className="rounded-lg border p-3">
                      <Moment
                        refTo={m}
                        quote={m.quote}
                        t={m.t}
                        side="ai"
                        note={
                          <>
                            {m.title && <span className="font-medium text-foreground">{m.title}. </span>}
                            Bot: {m.handling || 'no response recorded'}
                          </>
                        }
                        better={m.better}
                      />
                    </li>
                  ))}
                </ul>
                <div className="rounded-lg border border-dashed p-3">
                  <h5 className="mb-2 flex items-center gap-2 text-[13px] font-medium">
                    <SideLabel side="human" />
                    <span className="text-muted-foreground">— handled well</span>
                  </h5>
                  {o.human_example ? (
                    <Moment
                      refTo={o.human_example}
                      quote={o.human_example.quote}
                      t={o.human_example.t}
                      side="human"
                      note={o.human_example.handling}
                    />
                  ) : (
                    <p className="text-[13px] text-muted-foreground">No human example of this objection in this selection.</p>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </CompareSection>
  )
}
