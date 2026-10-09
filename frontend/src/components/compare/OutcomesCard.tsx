import type { ReactNode } from 'react'
import { OUTCOME_LABELS } from '@/lib/labels'
import type { CompareResult, Side, SideSignals } from '@/lib/types-compare'
import { CompareSection, SideLabel } from './CompareSection'
import { formatValue } from './format-value'
import { ValueBar } from './ValueBar'

/** F. Outcome distribution per side, then mood, objections, friction and escalation. */
export function OutcomesCard({ data }: { data: CompareResult }) {
  return (
    <CompareSection
      id="outcomes"
      title="Outcomes and customer mood"
      caption="How calls ended, and how customers felt."
    >
      {data.outcomes.length === 0 ? (
        <p className="text-muted-foreground">No reviewed calls with an outcome yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[22rem] text-left">
            <caption className="sr-only">Outcome as a percentage of reviewed calls</caption>
            <thead>
              <tr className="border-b text-xs text-muted-foreground">
                <th scope="col" className="py-2 pr-3 font-medium">Outcome</th>
                <th scope="col" className="w-[32%] px-3 py-2"><SideLabel side="ai" className="text-xs" /></th>
                <th scope="col" className="w-[32%] py-2 pl-3"><SideLabel side="human" className="text-xs" /></th>
              </tr>
            </thead>
            <tbody>
              {data.outcomes.map((o) => (
                <tr key={o.key} className="border-b last:border-0">
                  <th scope="row" className="py-2 pr-3 font-normal">{OUTCOME_LABELS[o.key] ?? o.label}</th>
                  <td className="px-3 py-2">
                    <ValueBar value={o.ai} max={100} side="ai" suffix="%" />
                  </td>
                  <td className="py-2 pl-3">
                    <ValueBar value={o.human} max={100} side="human" suffix="%" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h4 className="mt-6 mb-1 font-medium">Other signals</h4>
      <SignalsTable data={data} />
    </CompareSection>
  )
}

interface SignalRow {
  label: string
  value: (s: SideSignals, side: Side) => ReactNode
}

function moodText(s: SideSignals): string {
  const m = s.mood_end
  return `${m.positive ?? 0} positive, ${m.neutral ?? 0} neutral, ${m.negative ?? 0} negative`
}

function SignalsTable({ data }: { data: CompareResult }) {
  const reviewed = (side: Side) => data.scores[side].n
  const rows: SignalRow[] = [
    { label: 'Customer mood at the end', value: (s) => moodText(s) },
    { label: 'Mood improved during the call', value: (s, side) => `${s.mood_improved} of ${reviewed(side)} calls` },
    { label: 'Mood worsened during the call', value: (s, side) => `${s.mood_worsened} of ${reviewed(side)} calls` },
    {
      label: 'Objections handled well',
      value: (s) => (s.objections_total ? `${s.objections_handled_well} of ${s.objections_total}` : 'No objections'),
    },
    { label: 'Friction points per call', value: (s) => formatValue(s.friction_per_call) },
    { label: 'Questions left unanswered per call', value: (s) => formatValue(s.unanswered_per_call) },
    { label: 'Calls handed off or escalated', value: (s) => `${s.escalated_pct}%` },
    { label: 'Average intent score', value: (s) => (s.avg_intent === null ? '—' : `${s.avg_intent} / 100`) },
  ]

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[22rem] text-left">
        <caption className="sr-only">Other signals from the call reviews</caption>
        <thead>
          <tr className="border-b text-xs text-muted-foreground">
            <th scope="col" className="py-2 pr-3 font-medium">Signal</th>
            <th scope="col" className="w-[32%] px-3 py-2"><SideLabel side="ai" className="text-xs" /></th>
            <th scope="col" className="w-[32%] py-2 pl-3"><SideLabel side="human" className="text-xs" /></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.label} className="border-b last:border-0">
              <th scope="row" className="py-2 pr-3 font-normal">{r.label}</th>
              <td className="num px-3 py-2">{reviewed('ai') ? r.value(data.signals.ai, 'ai') : '—'}</td>
              <td className="num py-2 pl-3">{reviewed('human') ? r.value(data.signals.human, 'human') : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
