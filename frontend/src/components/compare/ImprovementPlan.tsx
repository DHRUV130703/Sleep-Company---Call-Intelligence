import { useState } from 'react'
import type { CompareResult, ImprovementParameter } from '@/lib/types-compare'
import { cn } from '@/lib/utils'
import { CompareSection, SideLabel } from './CompareSection'
import { formatValue } from './format-value'
import { AreaChip, BetterLine, Moment, PriorityPill, ToggleRow } from './ImprovementBits'
import { ValueBar } from './ValueBar'

/** Improvement plan: every review parameter ranked by how much fixing it would help, with proof per call. */
export function ImprovementPlan({ data }: { data: CompareResult }) {
  const params = data.improvement.parameters
  // Open the most important parameter by default so the page shows a worked example straight away.
  const [open, setOpen] = useState<Set<string>>(() => new Set(params[0]?.priority === 'high' ? [params[0].key] : []))
  const toggle = (key: string) =>
    setOpen((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })

  return (
    <CompareSection
      id="plan"
      title="Improvement plan for the bot"
      caption="Each review parameter, most important first. Gap = how far the bot is behind the human average; weak = bot calls scoring 1–2. Open a row to see the bot's weakest moments next to the best human ones."
    >
      {data.scores.ai.n === 0 ? (
        <p className="text-muted-foreground">No analysed bot calls in this selection.</p>
      ) : (
        <ol className="divide-y rounded-lg border">
          {params.map((p) => (
            <ParameterRow key={p.key} p={p} open={open.has(p.key)} onToggle={() => toggle(p.key)} />
          ))}
        </ol>
      )}
    </CompareSection>
  )
}

function ParameterRow({ p, open, onToggle }: { p: ImprovementParameter; open: boolean; onToggle: () => void }) {
  const id = `param-${p.key}`
  return (
    <li>
      <ToggleRow open={open} onToggle={onToggle} controls={id}>
        <div className="grid gap-2 md:grid-cols-[6rem_minmax(0,1fr)_14rem_8rem] md:items-center md:gap-4">
          <PriorityPill priority={p.priority} />
          <div className="min-w-0">
            <div className="font-semibold">{p.label}</div>
            <AreaChip area={p.area} />
          </div>
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="w-12 text-xs text-muted-foreground">Bot</span>
              <ValueBar value={p.ai} max={5} side="ai" />
            </div>
            <div className="flex items-center gap-2">
              <span className="w-12 text-xs text-muted-foreground">Humans</span>
              <ValueBar value={p.human} max={5} side="human" />
            </div>
          </div>
          <div className="num text-[13px]">
            <GapText gap={p.gap} />
            <div className="text-xs text-muted-foreground">
              weak in {p.weak_calls} of {p.of} bot {p.of === 1 ? 'call' : 'calls'}
            </div>
          </div>
        </div>
      </ToggleRow>
      {open && (
        <div id={id} className="space-y-4 border-t bg-surface px-3 py-4">
          {p.fix && <BetterLine label="How to fix" text={p.fix} />}
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-3">
              <h5 className="flex items-center gap-2 text-[13px] font-medium">
                <SideLabel side="ai" />
                <span className="text-muted-foreground">— where the bot fell short</span>
              </h5>
              {p.bot_examples.length === 0 ? (
                <p className="text-[13px] text-muted-foreground">No bot call scored 3 or lower here.</p>
              ) : (
                p.bot_examples.map((ex, i) => (
                  <Moment
                    key={`${ex.call_id}-${i}`}
                    refTo={ex}
                    quote={ex.quote}
                    t={ex.t}
                    side="ai"
                    note={
                      <>
                        <span className="num font-medium text-foreground">{ex.score}/5</span> — {ex.reason || 'No reason given'}
                      </>
                    }
                    better={ex.better}
                  />
                ))
              )}
            </div>
            <div className="space-y-3">
              <h5 className="flex items-center gap-2 text-[13px] font-medium">
                <SideLabel side="human" />
                <span className="text-muted-foreground">— what good looks like</span>
              </h5>
              {p.human_examples.length === 0 ? (
                <p className="text-[13px] text-muted-foreground">No human call scored 4+ with a verified quote here.</p>
              ) : (
                p.human_examples.map((ex, i) => (
                  <Moment
                    key={`${ex.call_id}-${i}`}
                    refTo={ex}
                    quote={ex.quote}
                    t={ex.t}
                    side="human"
                    note={
                      <>
                        <span className="num font-medium text-foreground">{ex.score}/5</span> — {ex.reason}
                      </>
                    }
                  />
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </li>
  )
}

function GapText({ gap }: { gap: number | null }) {
  if (gap === null) return <span className="text-muted-foreground">No bot score</span>
  if (gap > 0)
    return <span className={cn('font-semibold', gap >= 1 ? 'text-negative' : 'text-warning')}>{formatValue(gap)} behind</span>
  if (gap < 0) return <span className="font-semibold text-positive">{formatValue(-gap)} ahead</span>
  return <span className="font-semibold">Level</span>
}
