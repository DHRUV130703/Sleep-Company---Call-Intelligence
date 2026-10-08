// THE call screen (PRD §6.4 Conversations tab, §6.5 Call Detail). Used full-width on /calls/:id
// and embedded in Lead Details. Player on top; transcript on the left, insights on the right.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeftRight, CircleX, Loader2, MinusCircle, RotateCcw, Sparkles } from 'lucide-react'
import { useCallback, useRef, useState, type ReactNode } from 'react'
import { Link } from 'react-router'
import { AgentChip } from '@/components/AgentChip'
import { CallStatusPill } from '@/components/CallStatusPill'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { ApiError } from '@/lib/api'
import { callAudioUrl, callsApi } from '@/lib/api-calls'
import { formatClock, formatDateTime, humanize } from '@/lib/format'
import { OUTCOME_LABELS, STAGE_LABELS } from '@/lib/labels'
import type { CallDetail } from '@/lib/types-calls'
import { AudioPlayer, type AudioPlayerHandle, type WaveMarker } from './AudioPlayer'
import { CallTabs } from './CallTabs'
import { MOMENT_TONE } from './moments'
import { TranscriptView } from './TranscriptView'

const isProcessing = (c?: CallDetail) => c?.status === 'queued' || c?.status === 'running'

export function CallView({ callId }: { callId: number }) {
  // `key` resets the player position and transcript state when switching between calls.
  return <CallViewBody key={callId} callId={callId} />
}

function CallViewBody({ callId }: { callId: number }) {
  const call = useQuery({
    queryKey: ['call', callId],
    queryFn: () => callsApi.get(callId),
    enabled: Number.isFinite(callId) && callId > 0,
    refetchInterval: (q) => (isProcessing(q.state.data) ? 3000 : false),
  })
  const playerRef = useRef<AudioPlayerHandle>(null)
  const [time, setTime] = useState(0)
  const hasAudio = call.data?.has_audio ?? false

  const seek = useCallback(
    (t: number) => {
      if (hasAudio) playerRef.current?.seek(t)
      else setTime(t) // no audio: still move the transcript highlight
    },
    [hasAudio],
  )

  if (!(callId > 0)) return <ErrorBox error={new ApiError(404, 'NOT_FOUND', 'Call not found.')} />
  if (call.isPending) return <CallViewSkeleton />
  if (call.isError) return <ErrorBox error={call.error} />

  const c = call.data
  const markers: WaveMarker[] = (c.analysis?.key_moments ?? []).map((m) => ({
    t: m.t,
    label: m.label || humanize(m.type),
    tone: MOMENT_TONE[m.type] ?? 'muted',
  }))

  return (
    <div className="space-y-4">
      <CallHeader call={c} />
      <StatusNotice call={c} />
      <AudioPlayer
        ref={playerRef}
        src={c.has_audio ? callAudioUrl(c.id) : null}
        accent={c.agent_type}
        markers={markers}
        durationHint={c.duration_s}
        onTimeUpdate={setTime}
      />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <TranscriptView
          segments={c.transcript?.segments ?? []}
          hasOtherScript={c.transcript?.has_other_script ?? false}
          currentTime={time}
          accent={c.agent_type}
          onSeek={seek}
        />
        <CallTabs analysis={c.analysis} metrics={c.metrics} metricLabels={c.metric_labels} onSeek={seek} />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Header: what this call is, plus Retry / Re-analyse / Swap speakers
// ---------------------------------------------------------------------------

function CallHeader({ call: c }: { call: CallDetail }) {
  const outcome = c.outcome ? (OUTCOME_LABELS[c.outcome] ?? humanize(c.outcome)) : null
  return (
    <div className="flex flex-wrap items-start justify-between gap-4 rounded-xl border bg-surface p-4">
      <div className="min-w-0 space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="truncate font-mono text-lg font-semibold">{c.label}</h2>
          <AgentChip type={c.agent_type} />
          <CallStatusPill stage={c.stage} status={c.status} />
        </div>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-muted-foreground">
          {c.agent_name && <span>{c.agent_name}</span>}
          {c.lead && c.lead_id && (
            <Link to={`/leads/${c.lead_id}`} className="rounded-sm underline-offset-4 hover:underline focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none">
              Lead: {c.lead.name}
            </Link>
          )}
          {c.call_datetime && <span className="num">{formatDateTime(c.call_datetime)}</span>}
          {c.duration_s != null && <span className="num">{formatClock(c.duration_s)}</span>}
          {c.language && <span>{humanize(c.language)}</span>}
        </div>
        {(outcome || c.quality_pct != null) && (
          <div className="flex flex-wrap gap-x-4 gap-y-1">
            {outcome && (
              <span>
                <span className="text-muted-foreground">Outcome </span>
                <span className="font-medium">{outcome}</span>
              </span>
            )}
            {c.quality_pct != null && (
              <span>
                <span className="text-muted-foreground">Quality </span>
                <span className="num font-medium">{Math.round(c.quality_pct)}%</span>
              </span>
            )}
          </div>
        )}
      </div>
      <CallActions call={c} />
    </div>
  )
}

function CallActions({ call: c }: { call: CallDetail }) {
  const qc = useQueryClient()
  const action = useMutation({
    mutationFn: (fn: (id: number) => Promise<unknown>) => fn(c.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['call', c.id] })
      qc.invalidateQueries({ queryKey: ['calls'] })
    },
  })

  const busy = action.isPending || isProcessing(c)
  const run = (question: string, fn: (id: number) => Promise<unknown>) => {
    if (window.confirm(question)) action.mutate(fn)
  }

  return (
    <div className="flex flex-col items-start gap-2 sm:items-end">
      <div className="flex flex-wrap gap-2">
        {(c.status === 'failed' || c.status === 'skipped') && (
          <Button variant="outline" disabled={busy} onClick={() => run('Retry processing this call?', callsApi.retry)}>
            <RotateCcw />
            Retry
          </Button>
        )}
        {c.transcript && (
          <>
            <Button variant="outline" disabled={busy} onClick={() => run('Run the AI analysis again for this call?', callsApi.reanalyze)}>
              <Sparkles />
              Re-analyse
            </Button>
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => run('Swap Agent and Customer on every line? The call will be re-analysed.', callsApi.swapSpeakers)}
            >
              <ArrowLeftRight />
              Swap speakers
            </Button>
          </>
        )}
      </div>
      {action.isError && <ErrorBox error={action.error} />}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Status notices, errors, loading
// ---------------------------------------------------------------------------

function StatusNotice({ call: c }: { call: CallDetail }) {
  if (isProcessing(c)) {
    return (
      <Notice tone="info" icon={<Loader2 className="size-5 animate-spin" aria-hidden />}>
        <span aria-live="polite">
          {c.status === 'queued' ? 'Waiting in the queue' : (STAGE_LABELS[c.stage] ?? humanize(c.stage))}… This page
          updates automatically.
        </span>
      </Notice>
    )
  }
  if (c.status === 'failed' || c.status === 'skipped') {
    const failed = c.status === 'failed'
    const Icon = failed ? CircleX : MinusCircle
    return (
      <Notice tone={failed ? 'negative' : 'muted'} icon={<Icon className="size-5" aria-hidden />} role="alert">
        <div className="font-medium">
          {failed ? `Failed while ${(STAGE_LABELS[c.stage] ?? c.stage).toLowerCase()}` : 'Skipped'}
        </div>
        {c.error_message && <div className="break-words">{c.error_message}</div>}
        {c.error_code && <div className="font-mono text-xs opacity-80">{c.error_code}</div>}
      </Notice>
    )
  }
  return null
}

const NOTICE_TONE = {
  info: 'bg-ai-soft text-ai',
  negative: 'bg-negative-soft text-negative',
  muted: 'bg-surface-sunken text-muted-foreground',
}

function Notice(props: { tone: keyof typeof NOTICE_TONE; icon: ReactNode; role?: string; children: ReactNode }) {
  return (
    <div role={props.role} className={`flex items-start gap-3 rounded-xl px-4 py-3 ${NOTICE_TONE[props.tone]}`}>
      <span className="mt-0.5 shrink-0">{props.icon}</span>
      <div className="min-w-0 space-y-0.5">{props.children}</div>
    </div>
  )
}

function ErrorBox({ error }: { error: Error }) {
  const notFound = error instanceof ApiError && error.status === 404
  return (
    <div role="alert" className="flex items-start gap-2 rounded-lg bg-negative-soft px-3 py-2 text-negative">
      <CircleX className="mt-0.5 size-4 shrink-0" aria-hidden />
      <span className="font-medium">{notFound ? 'This call was not found. It may have been removed.' : error.message}</span>
    </div>
  )
}

function CallViewSkeleton() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Loading call">
      <Skeleton className="h-24 w-full rounded-xl" />
      <Skeleton className="h-28 w-full rounded-xl" />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Skeleton className="h-96 w-full rounded-xl" />
        <Skeleton className="h-96 w-full rounded-xl" />
      </div>
    </div>
  )
}
