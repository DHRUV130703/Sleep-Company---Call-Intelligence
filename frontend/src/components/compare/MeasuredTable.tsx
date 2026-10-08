import type { CompareResult } from '@/lib/types-compare'
import { CompareSection, SideLabel } from './CompareSection'
import { ValueBar } from './ValueBar'

/** E. Metrics counted in code from the transcript segments (PRD §7.2). Averages per call. */
export function MeasuredTable({ data }: { data: CompareResult }) {
  return (
    <CompareSection
      id="measured"
      title="Measured from the transcripts"
      caption="Counted directly from who said what, not judged by the model. Averages per call."
    >
      <div className="overflow-x-auto">
        <table className="w-full min-w-[22rem] text-left">
          <caption className="sr-only">Average per call for each measure, AI voice bot and human agents</caption>
          <thead>
            <tr className="border-b text-xs text-muted-foreground">
              <th scope="col" className="py-2 pr-3 font-medium">Measure</th>
              <th scope="col" className="w-[32%] px-3 py-2"><SideLabel side="ai" className="text-xs" /></th>
              <th scope="col" className="w-[32%] py-2 pl-3"><SideLabel side="human" className="text-xs" /></th>
            </tr>
          </thead>
          <tbody>
            {data.metrics.map((m) => {
              // Bars are normalised per row: the larger of the two values fills the bar.
              const max = Math.max(m.ai ?? 0, m.human ?? 0)
              return (
                <tr key={m.key} className="border-b last:border-0">
                  <th scope="row" className="py-2 pr-3 font-normal">{m.label}</th>
                  <td className="px-3 py-2">
                    <ValueBar value={m.ai} max={max} side="ai" />
                  </td>
                  <td className="py-2 pl-3">
                    <ValueBar value={m.human} max={max} side="human" />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </CompareSection>
  )
}
