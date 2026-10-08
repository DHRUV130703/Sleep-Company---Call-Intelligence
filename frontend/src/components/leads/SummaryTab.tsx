import { Link } from 'react-router'
import { AgentChip } from '@/components/AgentChip'
import { formatClock, formatDateTime } from '@/lib/format'
import { OUTCOME_LABELS } from '@/lib/labels'
import type { LeadCall } from '@/lib/types-leads'

/** Each call's summary, oldest first, so the story of the lead reads top to bottom. */
export function SummaryTab({ calls }: { calls: LeadCall[] }) {
  const inOrder = [...calls].reverse()
  if (inOrder.length === 0) return <p className="text-muted-foreground">No conversations for this lead yet.</p>
  return (
    <ol className="space-y-4">
      {inOrder.map((c, i) => (
        <li key={c.id} className="rounded-xl border bg-surface p-5">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="num grid size-6 place-items-center rounded-full bg-surface-sunken text-xs font-semibold">
              {i + 1}
            </span>
            <Link to={`/calls/${c.id}`} className="num font-medium hover:underline">
              {c.call_datetime ? formatDateTime(c.call_datetime) : c.label}
            </Link>
            <AgentChip type={c.agent_type} />
            {c.duration_s != null && <span className="num text-muted-foreground">{formatClock(c.duration_s)}</span>}
            {c.outcome && <span className="text-muted-foreground">· {OUTCOME_LABELS[c.outcome] ?? c.outcome}</span>}
          </div>
          {c.summary ? (
            <>
              {c.summary.one_liner && <p className="mt-3 font-medium">{c.summary.one_liner}</p>}
              <ul className="mt-2 list-disc space-y-1 pl-5">
                {(c.summary.bullets ?? []).map((b) => (
                  <li key={b}>{b}</li>
                ))}
              </ul>
            </>
          ) : (
            <p className="mt-3 text-muted-foreground">
              {c.status === 'failed' ? (c.error_message ?? 'This call could not be analysed.') : 'Not analysed yet.'}
            </p>
          )}
        </li>
      ))}
    </ol>
  )
}
