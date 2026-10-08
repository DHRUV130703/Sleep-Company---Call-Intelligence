import { useQuery } from '@tanstack/react-query'
import { Layers } from 'lucide-react'
import { Link } from 'react-router'
import { BatchProgressBar } from '@/components/BatchProgressBar'
import { EmptyState } from '@/components/EmptyState'
import { PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { batchesApi } from '@/lib/api-batches'
import { formatDateTime, formatHoursMins, humanize } from '@/lib/format'

export default function BatchesPage() {
  const batches = useQuery({
    queryKey: ['batches'],
    queryFn: batchesApi.list,
    refetchInterval: (q) => (q.state.data?.items.some((b) => b.status === 'processing') ? 3000 : false),
  })

  return (
    <>
      <PageHeader
        title="Batches"
        description="Every upload becomes a batch. Open one to follow its progress or see its results."
        actions={
          <Button asChild>
            <Link to="/upload">New upload</Link>
          </Button>
        }
      />
      {batches.isPending && <Skeleton className="h-48 w-full" />}
      {batches.isError && <p role="alert" className="text-negative">{batches.error.message}</p>}
      {batches.data && batches.data.items.length === 0 && (
        <EmptyState
          icon={Layers}
          title="No batches yet"
          description="Upload recordings to start your first batch."
          action={
            <Button asChild>
              <Link to="/upload">Upload recordings</Link>
            </Button>
          }
        />
      )}
      {batches.data && batches.data.items.length > 0 && (
        <ul className="divide-y rounded-xl border bg-surface">
          {batches.data.items.map((b) => {
            const finished = b.counts.done + b.counts.skipped + b.counts.failed
            return (
              <li key={b.id}>
                <Link
                  to={`/batches/${b.id}`}
                  className="grid gap-2 px-4 py-4 hover:bg-surface-sunken/50 focus-visible:outline-2 focus-visible:outline-ring sm:grid-cols-[minmax(0,1fr)_14rem] sm:items-center sm:gap-6"
                >
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-baseline gap-x-2">
                      <span className="truncate font-medium">{b.name}</span>
                      {b.campaign && <span className="text-xs text-muted-foreground">· {b.campaign}</span>}
                    </div>
                    <div className="num mt-0.5 text-xs text-muted-foreground">
                      {formatDateTime(b.created_at)} · {humanize(b.source_type)} · {b.counts.total} calls
                      {b.counts.ai > 0 && <span className="text-ai"> · AI {b.counts.ai}</span>}
                      {b.counts.human > 0 && <span className="text-human"> · Human {b.counts.human}</span>}
                      {b.counts.audio_seconds > 0 && ` · ${formatHoursMins(b.counts.audio_seconds)}`}
                    </div>
                  </div>
                  <div>
                    <BatchProgressBar counts={b.counts} />
                    <div className="num mt-1 text-xs text-muted-foreground">
                      {b.status === 'processing' ? `${finished} of ${b.counts.total} finished` : humanize(b.status)}
                      {b.counts.failed > 0 && <span className="text-negative"> · {b.counts.failed} failed</span>}
                    </div>
                  </div>
                </Link>
              </li>
            )
          })}
        </ul>
      )}
    </>
  )
}
