import { Layers } from 'lucide-react'
import { useSearchParams } from 'react-router'
import { AgentChip } from '@/components/AgentChip'
import { CallView } from '@/components/calls/CallView'
import { CallStatusPill } from '@/components/CallStatusPill'
import { formatClock, formatDateTime } from '@/lib/format'
import { OUTCOME_LABELS } from '@/lib/labels'
import type { LeadCall } from '@/lib/types-leads'
import { cn } from '@/lib/utils'

/**
 * Every recording of this lead's phone number, newest first. Picking one shows the full call
 * (player, transcript, scorecard) below. The chosen call is kept in `?call=` so it can be linked.
 */
export function ConversationsTab({ calls }: { calls: LeadCall[] }) {
  const [params, setParams] = useSearchParams()
  const picked = Number(params.get('call'))
  const current = calls.find((c) => c.id === picked) ?? calls[0]

  const choose = (id: number) =>
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.set('call', String(id))
        return next
      },
      { replace: true },
    )

  if (!current) return <p className="text-muted-foreground">No conversations for this lead yet.</p>

  return (
    <div className="space-y-4">
      <section aria-labelledby="calls-title" className="rounded-xl border bg-surface">
        <h3 id="calls-title" className="flex items-center gap-2 border-b px-4 py-3 font-semibold">
          <Layers className="size-4 text-muted-foreground" aria-hidden />
          <span className="num">{calls.length}</span> {calls.length === 1 ? 'conversation' : 'conversations'} with
          this number
        </h3>
        <ul className="divide-y">
          {calls.map((c) => {
            const active = c.id === current.id
            return (
              <li key={c.id}>
                <button
                  type="button"
                  aria-current={active ? 'true' : undefined}
                  onClick={() => choose(c.id)}
                  className={cn(
                    'flex w-full flex-wrap items-center gap-x-4 gap-y-1.5 px-4 py-3 text-left outline-none hover:bg-surface-sunken focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset',
                    active && 'bg-ai-soft/60 shadow-[inset_3px_0_0_var(--ai)]',
                  )}
                >
                  <span className="num min-w-36 font-medium">
                    {c.call_datetime ? formatDateTime(c.call_datetime) : '—'}
                  </span>
                  <AgentChip type={c.agent_type} />
                  <span className="num text-muted-foreground">
                    {c.duration_s != null ? formatClock(c.duration_s) : '—'}
                  </span>
                  <span>{c.outcome ? (OUTCOME_LABELS[c.outcome] ?? c.outcome) : '—'}</span>
                  <span className="num text-muted-foreground">
                    Quality {c.quality_pct != null ? `${Math.round(c.quality_pct)}%` : '—'}
                  </span>
                  <span className="ml-auto">
                    <CallStatusPill stage={c.stage} status={c.status} />
                  </span>
                  {c.one_liner && <span className="basis-full text-muted-foreground">{c.one_liner}</span>}
                </button>
              </li>
            )
          })}
        </ul>
      </section>

      <CallView key={current.id} callId={current.id} />
    </div>
  )
}
