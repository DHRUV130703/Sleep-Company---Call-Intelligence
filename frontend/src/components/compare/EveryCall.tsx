import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { CallStatusPill } from '@/components/CallStatusPill'
import { formatClock, humanize } from '@/lib/format'
import { OUTCOME_LABELS } from '@/lib/labels'
import type { CompareCall, CompareResult, Side } from '@/lib/types-compare'
import { cn } from '@/lib/utils'
import { CompareSection, SideLabel } from './CompareSection'

/** H. Every call in scope, grouped by side. Each label opens the call's review and transcript. */
export function EveryCall({ data }: { data: CompareResult }) {
  return (
    <CompareSection
      id="calls"
      title="Every call"
      caption="Each call in this selection. Open one to see its review, key moments and transcript."
    >
      <div className="space-y-6">
        <CallGroup side="ai" calls={data.calls.ai} />
        <CallGroup side="human" calls={data.calls.human} />
      </div>
    </CompareSection>
  )
}

function CallGroup({ side, calls }: { side: Side; calls: CompareCall[] }) {
  return (
    <div>
      <h4 className="mb-2 flex items-center gap-2">
        <SideLabel side={side} />
        <span className="num text-xs text-muted-foreground">
          {calls.length} {calls.length === 1 ? 'call' : 'calls'}
        </span>
      </h4>
      {calls.length === 0 ? (
        <p className="text-muted-foreground">No calls on this side in the current selection.</p>
      ) : (
        <ul className={cn('divide-y rounded-lg border border-l-2', side === 'ai' ? 'border-l-ai' : 'border-l-human')}>
          {calls.map((c) => (
            <CallRow key={c.id} call={c} />
          ))}
        </ul>
      )}
    </div>
  )
}

function CallRow({ call }: { call: CompareCall }) {
  const done = call.status === 'done'
  return (
    <li className="px-3 py-2.5">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <Link
          to={`/calls/${call.id}`}
          className="font-mono text-[13px] font-medium underline-offset-4 hover:underline focus-visible:underline"
        >
          {call.label}
        </Link>
        <Meta>{call.duration_s === null ? '—' : formatClock(call.duration_s)}</Meta>
        {done ? (
          <>
            {call.language && <Meta>{humanize(call.language)}</Meta>}
            {call.outcome && <Meta>{OUTCOME_LABELS[call.outcome] ?? humanize(call.outcome)}</Meta>}
            {call.quality_pct !== null && <Meta>Quality {Math.round(call.quality_pct)}%</Meta>}
          </>
        ) : (
          <>
            <CallStatusPill stage={call.status} status={call.status} />
            {call.error_code && <Meta>{humanize(call.error_code.toLowerCase())}</Meta>}
          </>
        )}
      </div>
      {call.one_liner && <p className="mt-1 text-muted-foreground">{call.one_liner}</p>}
    </li>
  )
}

function Meta({ children }: { children: ReactNode }) {
  return <span className="num text-xs text-muted-foreground">{children}</span>
}
