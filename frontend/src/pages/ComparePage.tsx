import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { GitCompareArrows, Info, RefreshCw } from 'lucide-react'
import { useMemo } from 'react'
import { Link, useSearchParams } from 'react-router'
import { AgentChip } from '@/components/AgentChip'
import { CallRcaList } from '@/components/compare/CallRcaList'
import { DifferencesTable } from '@/components/compare/DifferencesTable'
import { DivergingBars } from '@/components/compare/DivergingBars'
import { DownloadMenu } from '@/components/compare/DownloadMenu'
import { EveryCall } from '@/components/compare/EveryCall'
import { FixTheBot } from '@/components/compare/FixTheBot'
import { ImprovementPlan } from '@/components/compare/ImprovementPlan'
import { MeasuredTable } from '@/components/compare/MeasuredTable'
import { MissedObjections } from '@/components/compare/MissedObjections'
import { OutcomesCard } from '@/components/compare/OutcomesCard'
import { OutdatedReviewsNotice } from '@/components/compare/OutdatedReviewsNotice'
import { RecordsStrip } from '@/components/compare/RecordsStrip'
import { RootCauses } from '@/components/compare/RootCauses'
import { ScopePicker } from '@/components/compare/ScopePicker'
import { VerdictCard } from '@/components/compare/VerdictCard'
import { EmptyState } from '@/components/EmptyState'
import { PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { compareApi, scopeFromParams, scopeToParams } from '@/lib/api-compare'
import { formatDateTime } from '@/lib/format'
import type { CompareResult, CompareScope } from '@/lib/types-compare'
import { cn } from '@/lib/utils'

/** Report sections in page order: verdict and the bot improvement plan first, then the detail. Ids match each section's anchor. */
const SECTIONS = [
  { id: 'records', label: 'Records' },
  { id: 'verdict', label: 'Verdict' },
  { id: 'plan', label: 'Improvement plan' },
  { id: 'root-causes', label: 'Root causes' },
  { id: 'objections', label: 'Missed objections' },
  { id: 'fix', label: 'Recommended changes' },
  { id: 'call-rca', label: 'Call-by-call RCA' },
  { id: 'differences', label: 'Where they differ' },
  { id: 'scores', label: 'Review scores' },
  { id: 'measured', label: 'Measured' },
  { id: 'outcomes', label: 'Outcomes and mood' },
  { id: 'calls', label: 'Every call' },
]

export default function ComparePage() {
  const [params, setParams] = useSearchParams()
  const scope = useMemo(() => scopeFromParams(params), [params])
  const qc = useQueryClient()

  const compare = useQuery({
    queryKey: ['compare', scope],
    queryFn: () => compareApi.result(scope),
    // The backend caches per (scope, data version); the result only changes when calls change.
    staleTime: 10 * 60_000,
    refetchOnWindowFocus: false,
  })

  const rerun = useMutation({
    mutationFn: (s: CompareScope) => compareApi.result(s, true),
    onSuccess: (data, s) => {
      qc.setQueryData(['compare', s], data)
      qc.invalidateQueries({ queryKey: ['compare-options'] })
    },
  })

  const data = compare.data
  const hasCalls = !!data && data.records.ai.uploaded + data.records.human.uploaded > 0

  return (
    <>
      <PageHeader
        title="AI voice bot vs human agents"
        description={
          data
            ? `How good the bot is against your team, what to fix first, and the calls that prove it. Built ${formatDateTime(data.generated_at)}.`
            : 'How good the bot is against your team, what to fix first, and the calls that prove it.'
        }
        actions={
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              onClick={() => rerun.mutate(scope)}
              disabled={compare.isPending || rerun.isPending}
            >
              <RefreshCw className={cn('size-4', rerun.isPending && 'animate-spin motion-reduce:animate-none')} aria-hidden />
              Re-run comparison
            </Button>
            {hasCalls && <DownloadMenu scope={scope} />}
          </div>
        }
      />

      <ScopePicker scope={scope} onChange={(s) => setParams(scopeToParams(s), { replace: true })} />

      <div aria-live="polite" className="empty:hidden">
        {rerun.isPending && (
          <p className="mb-4 text-muted-foreground">Re-running the comparison — this can take up to a minute.</p>
        )}
        {rerun.isError && <ErrorLine error={rerun.error} />}
      </div>

      {compare.isPending && <ReportSkeleton />}
      {compare.isError && (
        <div className="space-y-3">
          <ErrorLine error={compare.error} />
          <Button variant="outline" onClick={() => compare.refetch()}>
            Try again
          </Button>
        </div>
      )}
      {data && !hasCalls && <NothingToCompare filtered={params.toString() !== ''} onClear={() => setParams({})} />}
      {data && hasCalls && <Report data={data} scope={scope} />}
    </>
  )
}

function Report({ data, scope }: { data: CompareResult; scope: CompareScope }) {
  return (
    <div className="xl:grid xl:grid-cols-[minmax(0,1fr)_11rem] xl:gap-8">
      <div className="min-w-0 space-y-6">
        <OneSideNotice data={data} />
        <OutdatedReviewsNotice data={data} scope={scope} />
        <RecordsStrip data={data} />
        <VerdictCard data={data} />
        <ImprovementPlan data={data} />
        <RootCauses data={data} />
        <MissedObjections data={data} />
        <FixTheBot data={data} />
        <CallRcaList data={data} />
        <DifferencesTable data={data} />
        <DivergingBars data={data} />
        <MeasuredTable data={data} />
        <OutcomesCard data={data} />
        <EveryCall data={data} />
      </div>
      <nav aria-label="Sections of this report" className="hidden xl:block">
        <div className="sticky top-24">
          <div className="mb-2 text-xs font-medium text-muted-foreground">On this page</div>
          <ol className="space-y-0.5 border-l">
            {SECTIONS.map((s) => (
              <li key={s.id}>
                <a
                  href={`#${s.id}`}
                  className="-ml-px block border-l border-transparent py-1 pl-3 text-[13px] text-muted-foreground hover:border-foreground hover:text-foreground"
                >
                  {s.label}
                </a>
              </li>
            ))}
          </ol>
        </div>
      </nav>
    </div>
  )
}

/** Shown when only one side has analysed calls: the report still renders, but can't compare. */
function OneSideNotice({ data }: { data: CompareResult }) {
  const aiReady = data.records.ai.analysed > 0
  const humanReady = data.records.human.analysed > 0
  if (aiReady && humanReady) return null

  const missing = !aiReady && !humanReady ? 'both' : aiReady ? 'human' : 'ai'
  const text =
    missing === 'both'
      ? 'No call in this selection has been analysed yet. The report fills in as calls finish processing.'
      : missing === 'ai'
        ? 'Only human agent calls have been analysed in this selection. Add AI voice bot calls (ideally the same campaign) to compare the two.'
        : 'Only AI voice bot calls have been analysed in this selection. Add human agent calls (ideally the same campaign) to compare the two.'

  return (
    <div role="status" className="flex flex-wrap items-start gap-3 rounded-xl border bg-surface px-4 py-3">
      <Info className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
      <p className="min-w-0 flex-1">{text}</p>
      <Button size="sm" variant="outline" asChild>
        <Link to="/upload">Upload recordings</Link>
      </Button>
    </div>
  )
}

function NothingToCompare({ filtered, onClear }: { filtered: boolean; onClear: () => void }) {
  return (
    <EmptyState
      icon={GitCompareArrows}
      title={filtered ? 'No calls match these filters' : 'Nothing to compare yet'}
      description={
        filtered
          ? 'Try other batches, another campaign or a wider date range.'
          : 'Upload calls from the AI voice bot and from human agents (ideally the same campaign). The comparison unlocks once each side has at least one analysed call.'
      }
      action={
        filtered ? (
          <Button variant="outline" onClick={onClear}>
            Clear filters
          </Button>
        ) : (
          <Button asChild>
            <Link to="/upload">Upload recordings</Link>
          </Button>
        )
      }
    >
      <div className="mt-5 flex items-center gap-2">
        <AgentChip type="ai" />
        <span className="text-muted-foreground">vs</span>
        <AgentChip type="human" />
      </div>
    </EmptyState>
  )
}

function ReportSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true">
      <p role="status" className="flex items-center gap-2 text-muted-foreground">
        <RefreshCw className="size-4 animate-spin motion-reduce:animate-none" aria-hidden />
        Building the comparison — this takes up to a minute the first time.
      </p>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} className="h-20" />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-[1fr_auto]">
        <Skeleton className="h-28" />
        <div className="grid grid-cols-2 gap-4">
          <Skeleton className="h-28 w-40" />
          <Skeleton className="h-28 w-40" />
        </div>
      </div>
      <Skeleton className="h-64" />
      <Skeleton className="h-80" />
      <Skeleton className="h-64" />
    </div>
  )
}

function ErrorLine({ error }: { error: Error }) {
  return (
    <div role="alert" className="mb-4 rounded-lg bg-negative-soft px-3 py-2 text-negative">
      {error.message}
    </div>
  )
}
