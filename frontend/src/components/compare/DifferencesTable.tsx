import type { CompareResult, Difference } from '@/lib/types-compare'
import { CompareSection, SideLabel } from './CompareSection'
import { EvidenceQuote } from './EvidenceQuote'

/** C. Themes where the bot and the team behave differently, each backed by verified quotes. */
export function DifferencesTable({ data }: { data: CompareResult }) {
  const rows = data.synthesis?.differences ?? []

  return (
    <CompareSection
      id="differences"
      title="Where they differ"
      caption="Written by the AI. Click a quote to hear it."
    >
      {!data.synthesis ? (
        <p className="text-muted-foreground">{data.synthesis_error ?? 'Not available for this selection.'}</p>
      ) : rows.length === 0 ? (
        <p className="text-muted-foreground">No clear differences with verified evidence were found.</p>
      ) : (
        <>
          {/* Tablet and up: a real table */}
          <div className="hidden overflow-x-auto md:block">
            <table className="w-full border-collapse text-left align-top">
              <thead>
                <tr className="border-b text-xs text-muted-foreground">
                  <th scope="col" className="w-[16%] py-2 pr-3 font-medium">Theme</th>
                  <th scope="col" className="w-[24%] px-3 py-2"><SideLabel side="ai" className="text-xs" /></th>
                  <th scope="col" className="w-[24%] px-3 py-2"><SideLabel side="human" className="text-xs" /></th>
                  <th scope="col" className="py-2 pl-3 font-medium">Why it matters</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((d) => (
                  <tr key={d.theme} className="border-b align-top last:border-0">
                    <th scope="row" className="py-3 pr-3 font-medium">{d.theme}</th>
                    <td className="px-3 py-3">
                      <div className="border-l-2 border-ai pl-3">{d.ai}</div>
                    </td>
                    <td className="px-3 py-3">
                      <div className="border-l-2 border-human pl-3">{d.human}</div>
                    </td>
                    <td className="py-3 pl-3">
                      <p>{d.why}</p>
                      <EvidenceList d={d} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Phone: one card per theme */}
          <ul className="space-y-4 md:hidden">
            {rows.map((d) => (
              <li key={d.theme} className="space-y-3 rounded-lg border p-3">
                <h4 className="font-semibold">{d.theme}</h4>
                <div className="border-l-2 border-ai pl-3">
                  <SideLabel side="ai" className="text-xs" />
                  <p className="mt-0.5">{d.ai}</p>
                </div>
                <div className="border-l-2 border-human pl-3">
                  <SideLabel side="human" className="text-xs" />
                  <p className="mt-0.5">{d.human}</p>
                </div>
                <div>
                  <div className="text-xs font-medium text-muted-foreground">Why it matters</div>
                  <p className="mt-0.5">{d.why}</p>
                  <EvidenceList d={d} />
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </CompareSection>
  )
}

function EvidenceList({ d }: { d: Difference }) {
  if (d.evidence.length === 0) return null
  return (
    <ul className="mt-2 space-y-1.5" aria-label={`Evidence for ${d.theme}`}>
      {d.evidence.map((ev, i) => (
        <li key={`${ev.call_id}-${i}`}>
          <EvidenceQuote callId={ev.call_id} label={ev.label} quote={ev.quote} t={ev.t} side={ev.agent_type} />
        </li>
      ))}
    </ul>
  )
}
