import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, GitCompareArrows, Layers, MessagesSquare, RotateCcw, Square } from 'lucide-react'
import { Link, useParams } from 'react-router'
import { AgentChip } from '@/components/AgentChip'
import { BatchProgressBar } from '@/components/BatchProgressBar'
import { CallStatusPill } from '@/components/CallStatusPill'
import { EmptyState } from '@/components/EmptyState'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { ApiError } from '@/lib/api'
import { batchesApi } from '@/lib/api-batches'
import { formatClock, formatDateTime } from '@/lib/format'
import { OUTCOME_LABELS } from '@/lib/labels'
import { useBatchEvents } from '@/lib/sse'
import type { BatchCall, BatchDetail, BatchEvent } from '@/lib/types-batches'

export default function BatchDetailPage() {
  const batchId = Number(useParams().batchId)
  const qc = useQueryClient()
  const key = ['batch', batchId]

  // Apply one live progress event to the cached batch (no refetch needed).
  function applyEvent(e: BatchEvent) {
    qc.setQueryData<BatchDetail>(key, (old) => {
      if (!old) return old
      const calls = old.calls.map((c) =>
        c.id === e.call_id ? { ...c, stage: e.stage, status: e.status, message: e.message } : c,
      )
      return { ...old, calls, counts: recount(old, calls), last_event_id: e.event_id }
    })
    if (e.status === 'done' || e.status === 'failed' || e.status === 'skipped') {
      void qc.invalidateQueries({ queryKey: key }) // pick up outcome, quality and errors
    }
  }

  const { live } = useBatchEvents(
    batchId,
    qc.getQueryData<BatchDetail>(key)?.last_event_id,
    qc.getQueryData<BatchDetail>(key)?.status === 'processing',
    (e) => applyEvent(e),
    () => void qc.invalidateQueries({ queryKey: key }),
  )

  const batch = useQuery({
    queryKey: key,
    queryFn: () => batchesApi.get(batchId),
    // SSE keeps rows live; a slow refresh keeps counts/ETA right. Poll fast only if SSE dropped.
    refetchInterval: (q) => (q.state.data?.status !== 'processing' ? false : live ? 10_000 : 3000),
  })

  const retryAll = useMutation({ mutationFn: () => batchesApi.retryFailed(batchId), onSuccess: () => qc.invalidateQueries({ queryKey: key }) })
  const cancel = useMutation({ mutationFn: () => batchesApi.cancel(batchId), onSuccess: () => qc.invalidateQueries({ queryKey: key }) })

  if (batch.isPending) return <Skeleton className="h-96 w-full" />
  if (batch.isError) {
    const notFound = batch.error instanceof ApiError && batch.error.status === 404
    return (
      <EmptyState
        icon={Layers}
        title={notFound ? `Batch #${batchId} not found` : 'Couldn’t load this batch'}
        description={notFound ? 'It may have been deleted, or the link is wrong.' : batch.error.message}
        action={<Button variant="outline" asChild><Link to="/batches">All batches</Link></Button>}
      />
    )
  }

  const b = batch.data
  const finished = b.counts.done + b.counts.skipped + b.counts.failed
  const sides = (['ai', 'human'] as const).filter((s) => b.calls.some((c) => c.agent_type === s))

  return (
    <div className="space-y-6">
      <Link to="/batches" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> All batches
      </Link>

      <Card>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h2 className="text-2xl font-semibold tracking-tight">{b.name}</h2>
              <p className="text-muted-foreground">
                {b.campaign && `${b.campaign} · `}Started {formatDateTime(b.created_at)}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {b.counts.failed > 0 && (
                <Button variant="outline" onClick={() => retryAll.mutate()} disabled={retryAll.isPending}>
                  <RotateCcw className="size-4" /> Retry all failed ({b.counts.failed})
                </Button>
              )}
              {b.status === 'processing' && b.counts.queued > 0 && (
                <Button variant="outline" onClick={() => window.confirm('Stop the calls that haven’t started yet?') && cancel.mutate()}>
                  <Square className="size-4" /> Cancel remaining
                </Button>
              )}
              <Button variant="outline" asChild>
                <Link to={`/leads?batch_id=${b.id}`}><MessagesSquare className="size-4" /> View conversations</Link>
              </Button>
              {b.counts.ai > 0 && b.counts.human > 0 && (
                <Button asChild>
                  <Link to={`/compare?batch_ids=${b.id}`}><GitCompareArrows className="size-4" /> Compare AI vs Human</Link>
                </Button>
              )}
            </div>
          </div>

          <BatchProgressBar counts={b.counts} className="h-2.5" />
          <div className="num flex flex-wrap gap-x-5 gap-y-1 text-sm" aria-live="polite">
            <span className="font-medium">
              {b.status === 'processing' ? `${finished} of ${b.counts.total} finished` : b.status === 'done' ? 'Done. Results are below.' : 'Cancelled'}
            </span>
            <span className="text-positive">{b.counts.done} analysed</span>
            {b.counts.running > 0 && <span className="text-ai">{b.counts.running} in progress</span>}
            {b.counts.queued > 0 && <span className="text-muted-foreground">{b.counts.queued} waiting</span>}
            {b.counts.skipped > 0 && <span className="text-muted-foreground">{b.counts.skipped} not connected</span>}
            {b.counts.failed > 0 && <span className="text-negative">{b.counts.failed} failed</span>}
            {b.eta_seconds != null && <span className="text-muted-foreground">about {formatClock(b.eta_seconds)} left</span>}
            {b.status === 'processing' && !live && <span className="text-warning">Live updates reconnecting…</span>}
          </div>
          {b.skipped_inputs.length > 0 && (
            <details className="text-sm">
              <summary className="cursor-pointer text-muted-foreground">
                {b.skipped_inputs.length} input{b.skipped_inputs.length > 1 && 's'} skipped before processing
              </summary>
              <ul className="mt-2 space-y-0.5 text-muted-foreground">
                {b.skipped_inputs.map((s, i) => <li key={i}>{s.name}: {s.reason}</li>)}
              </ul>
            </details>
          )}
        </CardContent>
      </Card>

      <div className={sides.length > 1 ? 'grid gap-6 lg:grid-cols-2' : ''}>
        {sides.map((side) => (
          <section key={side} aria-label={side === 'ai' ? 'AI voice bot calls' : 'Human agent calls'}>
            <div className="mb-2 flex items-center gap-2">
              <AgentChip type={side} />
              <span className="num text-sm text-muted-foreground">{b.calls.filter((c) => c.agent_type === side).length} calls</span>
            </div>
            <ul className={`divide-y rounded-xl border border-t-2 bg-surface ${side === 'ai' ? 'border-t-ai' : 'border-t-human'}`}>
              {b.calls.filter((c) => c.agent_type === side).map((c) => <CallRow key={c.id} call={c} batchKey={key} />)}
            </ul>
          </section>
        ))}
      </div>
    </div>
  )
}

function CallRow({ call: c, batchKey }: { call: BatchCall; batchKey: unknown[] }) {
  const qc = useQueryClient()
  const retry = useMutation({ mutationFn: () => batchesApi.retryCall(c.id), onSuccess: () => qc.invalidateQueries({ queryKey: batchKey }) })
  const problem = c.status === 'failed' || c.status === 'skipped'
  return (
    <li className="px-4 py-3">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        {c.status === 'done' ? (
          <Link to={`/calls/${c.id}`} className="min-w-0 flex-1 truncate font-medium hover:underline">{c.label}</Link>
        ) : (
          <span className="min-w-0 flex-1 truncate font-medium">{c.label}</span>
        )}
        {c.duration_s != null && <span className="num text-xs text-muted-foreground">{formatClock(c.duration_s)}</span>}
        {c.outcome && <span className="text-xs text-muted-foreground">{OUTCOME_LABELS[c.outcome] ?? c.outcome}</span>}
        {c.quality_pct != null && <span className="num text-xs text-muted-foreground">Q {Math.round(c.quality_pct)}%</span>}
        <CallStatusPill stage={c.stage} status={c.status} />
      </div>
      {(problem || (c.status !== 'done' && c.message)) && (
        <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
          <span className={c.status === 'failed' ? 'text-negative' : 'text-muted-foreground'}>
            {problem ? c.error_message ?? c.message : c.message}
          </span>
          {problem && c.error_code !== 'TOO_SHORT' && c.error_code !== 'CANCELLED' && (
            <Button variant="outline" size="sm" className="h-6 px-2 text-xs" onClick={() => retry.mutate()} disabled={retry.isPending}>
              Retry
            </Button>
          )}
        </div>
      )}
    </li>
  )
}

function recount(b: BatchDetail, calls: BatchCall[]) {
  const counts = { ...b.counts, queued: 0, running: 0, done: 0, failed: 0, skipped: 0 }
  for (const c of calls) counts[c.status] += 1
  return counts
}
