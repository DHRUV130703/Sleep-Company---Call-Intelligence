import { CircleCheck, CircleX, Play } from 'lucide-react'
import { Link } from 'react-router'
import { formatClock, humanize } from '@/lib/format'
import type { Objection } from '@/lib/types-leads'

/** One objection: title, type tag, the customer's words (click to hear it), how it was handled. */
export function ObjectionCard({ objection: o }: { objection: Objection }) {
  const at = o.t != null ? Math.floor(o.t) : null
  const href = at != null ? `/calls/${o.call_id}?t=${at}` : `/calls/${o.call_id}`
  return (
    <article className="rounded-lg border p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h4 className="font-medium">{o.title}</h4>
        <span className="rounded-full bg-surface-sunken px-2 py-0.5 text-xs">{humanize(o.type)}</span>
      </div>

      {o.customer_quote && (
        <Link
          to={href}
          className="group mt-2 flex gap-2 rounded-md border-l-2 border-human bg-human-soft/50 px-3 py-2 outline-none hover:bg-human-soft focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Play className="mt-0.5 size-3.5 shrink-0 text-human" aria-hidden />
          <span className="min-w-0">
            <span className="italic">“{o.customer_quote}”</span>
            <span className="mt-0.5 block font-mono text-xs text-muted-foreground">
              {o.call_label}
              {at != null && ` · ${formatClock(at)}`}
              <span className="sr-only"> — open the call at this moment</span>
            </span>
          </span>
        </Link>
      )}

      <dl className="mt-3 space-y-2">
        <div>
          <dt className="text-xs text-muted-foreground">How this objection was handled?</dt>
          <dd className="mt-0.5 flex gap-1.5">
            <Verdict ok={o.handled_well} yes="Handled well" no="Handled poorly" />
            <span>{o.handling || '—'}</span>
          </dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Was the customer satisfied?</dt>
          <dd className="mt-0.5 flex gap-1.5">
            <Verdict ok={o.customer_satisfied} yes="Yes" no="No" />
            <span>{o.customer_satisfied ? 'Yes, the customer seemed satisfied.' : 'No, the concern was left open.'}</span>
          </dd>
        </div>
        {o.better_response && (
          <div>
            <dt className="text-xs text-muted-foreground">A better response</dt>
            <dd className="mt-0.5">{o.better_response}</dd>
          </div>
        )}
      </dl>
    </article>
  )
}

function Verdict({ ok, yes, no }: { ok: boolean; yes: string; no: string }) {
  return ok ? (
    <CircleCheck className="mt-0.5 size-4 shrink-0 text-positive" aria-label={yes} />
  ) : (
    <CircleX className="mt-0.5 size-4 shrink-0 text-negative" aria-label={no} />
  )
}
