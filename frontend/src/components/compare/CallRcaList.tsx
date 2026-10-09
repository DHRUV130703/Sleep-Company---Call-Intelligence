import { useMemo, useState } from 'react'
import { formatClock, humanize } from '@/lib/format'
import { OUTCOME_LABELS } from '@/lib/labels'
import type { CallIssue, CallRca, CompareResult } from '@/lib/types-compare'
import { cn } from '@/lib/utils'
import { CompareSection } from './CompareSection'
import { BetterLine, CallLinks, ToggleRow } from './ImprovementBits'
import { EvidenceQuote } from './EvidenceQuote'

type Kind = CallIssue['kind']
const KINDS: { key: Kind | 'all'; label: string }[] = [
  { key: 'all', label: 'All issues' },
  { key: 'failure', label: 'Bot failures' },
  { key: 'objection', label: 'Objections' },
  { key: 'weak_score', label: 'Weak scores' },
  { key: 'unanswered', label: 'Unanswered questions' },
]
const KIND_STYLE: Record<Kind, string> = {
  failure: 'bg-negative-soft text-negative',
  objection: 'bg-warning-soft text-warning',
  weak_score: 'bg-ai-soft text-ai',
  unanswered: 'bg-surface-sunken text-muted-foreground',
}
const KIND_LABEL: Record<Kind, string> = {
  failure: 'Failure',
  objection: 'Objection',
  weak_score: 'Weak score',
  unanswered: 'Unanswered',
}

/** Call-by-call RCA: every bot call, worst first, with its issues on the call's timeline. */
export function CallRcaList({ data }: { data: CompareResult }) {
  const calls = data.improvement.call_rca
  const [kind, setKind] = useState<Kind | 'all'>('all')
  const [open, setOpen] = useState<number | null>(calls[0]?.call_id ?? null)
  const counts = useMemo(() => {
    const c: Record<string, number> = { all: 0 }
    for (const call of calls)
      for (const i of call.issues) {
        c.all += 1
        c[i.kind] = (c[i.kind] ?? 0) + 1
      }
    return c
  }, [calls])

  if (data.scores.ai.n === 0) return null
  return (
    <CompareSection
      id="call-rca"
      title="Call-by-call RCA (bot calls)"
      caption="Bot calls, worst first. Open one to see what went wrong and when."
    >
      <div role="group" aria-label="Filter issues" className="mb-3 flex flex-wrap gap-1.5">
        {KINDS.map((k) => (
          <button
            key={k.key}
            type="button"
            onClick={() => setKind(k.key)}
            aria-pressed={kind === k.key}
            className={cn(
              'rounded-full border px-2.5 py-1 text-xs focus-visible:outline-2 focus-visible:outline-ring',
              kind === k.key ? 'border-foreground bg-foreground text-background' : 'hover:bg-accent',
            )}
          >
            {k.label} <span className="num opacity-70">{counts[k.key] ?? 0}</span>
          </button>
        ))}
      </div>
      <ol className="divide-y rounded-lg border">
        {calls.map((c) => (
          <CallRow
            key={c.call_id}
            call={c}
            kind={kind}
            open={open === c.call_id}
            onToggle={() => setOpen(open === c.call_id ? null : c.call_id)}
          />
        ))}
      </ol>
    </CompareSection>
  )
}

function CallRow({ call, kind, open, onToggle }: { call: CallRca; kind: Kind | 'all'; open: boolean; onToggle: () => void }) {
  const id = `rca-${call.call_id}`
  const issues = kind === 'all' ? call.issues : call.issues.filter((i) => i.kind === kind)
  return (
    <li>
      <ToggleRow open={open} onToggle={onToggle} controls={id}>
        <div className="grid gap-1.5 md:grid-cols-[minmax(0,1fr)_5rem_10rem_minmax(0,14rem)] md:items-center md:gap-4">
          <div className="min-w-0">
            <div className="truncate font-mono text-[13px] font-medium">{call.label}</div>
            {call.one_liner && <div className="truncate text-xs text-muted-foreground">{call.one_liner}</div>}
          </div>
          <div className="num">
            <span className={cn('font-semibold', (call.review_score ?? 5) < 2.5 ? 'text-negative' : (call.review_score ?? 5) < 3.5 ? 'text-warning' : 'text-positive')}>
              {call.review_score === null ? '—' : call.review_score.toFixed(1)}
            </span>
            <span className="text-xs text-muted-foreground"> / 5</span>
          </div>
          <div className="text-[13px] text-muted-foreground">
            {call.outcome ? (OUTCOME_LABELS[call.outcome] ?? humanize(call.outcome)) : '—'}
          </div>
          <div className="min-w-0 text-[13px]">
            <span className="num font-medium">{call.issue_count} {call.issue_count === 1 ? 'issue' : 'issues'}</span>
            {call.main_issue && <span className="block truncate text-xs text-muted-foreground">{call.main_issue}</span>}
          </div>
        </div>
      </ToggleRow>
      {open && (
        <div id={id} className="space-y-3 border-t bg-surface px-3 py-4">
          <CallLinks refTo={call} />
          {issues.length === 0 ? (
            <p className="text-[13px] text-muted-foreground">No issues of this kind in this call.</p>
          ) : (
            <ol className="space-y-3 border-l pl-4">
              {issues.map((i, n) => (
                <IssueItem key={n} issue={i} call={call} />
              ))}
            </ol>
          )}
        </div>
      )}
    </li>
  )
}

function IssueItem({ issue, call }: { issue: CallIssue; call: CallRca }) {
  return (
    <li className="relative space-y-1.5">
      <span className="absolute top-1.5 -left-[21px] size-2.5 rounded-full border-2 border-background bg-ai" aria-hidden />
      <div className="flex flex-wrap items-center gap-2">
        <span className="num w-10 font-mono text-xs text-muted-foreground">{issue.t >= 0 ? formatClock(Math.floor(issue.t)) : '—'}</span>
        <span className={cn('rounded-full px-2 py-0.5 text-xs font-medium', KIND_STYLE[issue.kind])}>{KIND_LABEL[issue.kind]}</span>
        <span className="font-medium">{issue.title}</span>
      </div>
      {issue.detail && <p className="text-[13px] text-muted-foreground">{issue.detail}</p>}
      {issue.quote && <EvidenceQuote callId={call.call_id} label={call.label} quote={issue.quote} t={issue.t} side="ai" />}
      <BetterLine text={issue.better} />
    </li>
  )
}
