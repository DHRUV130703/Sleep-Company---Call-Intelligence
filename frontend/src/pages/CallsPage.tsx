import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Phone, RotateCcw, Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { AgentChip } from '@/components/AgentChip'
import { CallStatusPill } from '@/components/CallStatusPill'
import { EmptyState } from '@/components/EmptyState'
import { IntentPill } from '@/components/IntentPill'
import { PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { callsApi } from '@/lib/api-calls'
import { formatClock, formatDateTime, humanize } from '@/lib/format'
import { OUTCOME_LABELS } from '@/lib/labels'
import type { AgentType, CallFilters, CallRow, CallStatus } from '@/lib/types-calls'

const PAGE_SIZE = 50
const linkClass = 'rounded-sm underline-offset-4 hover:underline focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none'

// PRD §6.5: a flat table of every recording.
export default function CallsPage() {
  const [search, setSearch] = useState('')
  const [q, setQ] = useState('')
  const [agentType, setAgentType] = useState<'all' | AgentType>('all')
  const [status, setStatus] = useState<'all' | CallStatus>('all')
  const [page, setPage] = useState(1)

  // Wait until typing pauses before searching.
  useEffect(() => {
    const id = setTimeout(() => {
      setQ(search.trim())
      setPage(1)
    }, 300)
    return () => clearTimeout(id)
  }, [search])

  const filters: CallFilters = {
    q: q || undefined,
    agent_type: agentType === 'all' ? undefined : agentType,
    status: status === 'all' ? undefined : status,
    page,
    page_size: PAGE_SIZE,
  }
  const calls = useQuery({
    queryKey: ['calls', filters],
    queryFn: () => callsApi.list(filters),
    placeholderData: keepPreviousData,
    refetchInterval: (query) =>
      query.state.data?.items.some((c) => c.status === 'queued' || c.status === 'running') ? 5000 : false,
  })

  const hasFilters = Boolean(q) || agentType !== 'all' || status !== 'all'
  const clearFilters = () => {
    setSearch('')
    setQ('')
    setAgentType('all')
    setStatus('all')
    setPage(1)
  }

  return (
    <>
      <PageHeader title="Calls" description="Every recording, its status, outcome and quality score." />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative w-full sm:w-72">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search label, agent or campaign"
            aria-label="Search calls"
            className="pl-8"
          />
        </div>
        <Select
          value={agentType}
          onValueChange={(v) => {
            setAgentType(v as typeof agentType)
            setPage(1)
          }}
        >
          <SelectTrigger aria-label="Agent type">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All agents</SelectItem>
            <SelectItem value="ai">AI voice bot</SelectItem>
            <SelectItem value="human">Human agents</SelectItem>
          </SelectContent>
        </Select>
        <Select
          value={status}
          onValueChange={(v) => {
            setStatus(v as typeof status)
            setPage(1)
          }}
        >
          <SelectTrigger aria-label="Status">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="done">Done</SelectItem>
            <SelectItem value="running">Processing</SelectItem>
            <SelectItem value="queued">Queued</SelectItem>
            <SelectItem value="failed">Failed</SelectItem>
            <SelectItem value="skipped">Not connected</SelectItem>
          </SelectContent>
        </Select>
        {hasFilters && (
          <Button variant="ghost" onClick={clearFilters}>
            Clear filters
          </Button>
        )}
      </div>

      {calls.isPending && <TableSkeleton />}
      {calls.isError && (
        <div role="alert" className="rounded-lg bg-negative-soft px-3 py-2 font-medium text-negative">
          {calls.error.message}
        </div>
      )}
      {calls.data && calls.data.total === 0 && (
        hasFilters ? (
          <EmptyState
            icon={Search}
            title="No calls match these filters"
            description="Try a different search, or clear the filters."
            action={<Button variant="outline" onClick={clearFilters}>Clear filters</Button>}
          />
        ) : (
          <EmptyState
            icon={Phone}
            title="No calls yet"
            description="Upload recordings and they'll be listed here as they're processed."
            action={
              <Button asChild>
                <Link to="/upload">Upload recordings</Link>
              </Button>
            }
          />
        )
      )}
      {calls.data && calls.data.total > 0 && (
        <>
          <div className="rounded-xl border bg-surface">
            <CallsTable rows={calls.data.items} />
          </div>
          <Pagination page={page} total={calls.data.total} onPage={setPage} />
        </>
      )}
    </>
  )
}

function CallsTable({ rows }: { rows: CallRow[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Call</TableHead>
          <TableHead>Agent</TableHead>
          <TableHead>Lead</TableHead>
          <TableHead>Date</TableHead>
          <TableHead className="text-right">Duration</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Outcome</TableHead>
          <TableHead>Intent</TableHead>
          <TableHead className="text-right">Quality</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((c) => (
          <TableRow key={c.id}>
            <TableCell>
              <Link to={`/calls/${c.id}`} className={`font-mono font-medium ${linkClass}`}>
                {c.label}
              </Link>
            </TableCell>
            <TableCell>
              <AgentChip type={c.agent_type} />
            </TableCell>
            <TableCell>
              {c.lead_id ? (
                <Link to={`/leads/${c.lead_id}`} className={linkClass}>
                  {c.lead_name || `Lead #${c.lead_id}`}
                </Link>
              ) : (
                <span className="text-muted-foreground">—</span>
              )}
            </TableCell>
            <TableCell className="num">{c.call_datetime ? formatDateTime(c.call_datetime) : '—'}</TableCell>
            <TableCell className="num text-right">{c.duration_s != null ? formatClock(c.duration_s) : '—'}</TableCell>
            <TableCell>
              <div className="flex items-center gap-2">
                <span title={c.status === 'failed' ? (c.error_message ?? undefined) : undefined}>
                  <CallStatusPill stage={c.stage} status={c.status} />
                </span>
                {c.status === 'failed' && <RetryButton call={c} />}
              </div>
            </TableCell>
            <TableCell>{c.outcome ? (OUTCOME_LABELS[c.outcome] ?? humanize(c.outcome)) : '—'}</TableCell>
            <TableCell>
              <IntentPill bucket={c.intent_bucket} score={c.intent_score} short />
            </TableCell>
            <TableCell className="num text-right">{c.quality_pct != null ? `${Math.round(c.quality_pct)}%` : '—'}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

/** Re-queues a failed call from the stage where it stopped. The table refreshes itself while it runs. */
function RetryButton({ call }: { call: CallRow }) {
  const qc = useQueryClient()
  const retry = useMutation({
    mutationFn: () => callsApi.retry(call.id),
    onSettled: () => qc.invalidateQueries({ queryKey: ['calls'] }),
  })
  return (
    <Button
      variant="outline"
      size="sm"
      className="h-6 gap-1 px-2 text-xs"
      onClick={() => retry.mutate()}
      disabled={retry.isPending}
      aria-label={`Retry ${call.label}`}
      title={retry.isError ? retry.error.message : (call.error_message ?? 'Try this call again')}
    >
      <RotateCcw className={retry.isPending ? 'size-3 animate-spin motion-reduce:animate-none' : 'size-3'} aria-hidden />
      Retry
    </Button>
  )
}

function Pagination({ page, total, onPage }: { page: number; total: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const from = (page - 1) * PAGE_SIZE + 1
  const to = Math.min(page * PAGE_SIZE, total)
  return (
    <div className="mt-3 flex items-center justify-between gap-2 text-muted-foreground">
      <span className="num">
        {from}–{to} of {total} calls
      </span>
      {pages > 1 && (
        <div className="flex items-center gap-1">
          <Button variant="outline" size="icon" aria-label="Previous page" disabled={page <= 1} onClick={() => onPage(page - 1)}>
            <ChevronLeft />
          </Button>
          <span className="num px-2">
            {page} / {pages}
          </span>
          <Button variant="outline" size="icon" aria-label="Next page" disabled={page >= pages} onClick={() => onPage(page + 1)}>
            <ChevronRight />
          </Button>
        </div>
      )}
    </div>
  )
}

function TableSkeleton() {
  return (
    <div className="space-y-2 rounded-xl border bg-surface p-4" aria-busy="true" aria-label="Loading calls">
      {Array.from({ length: 8 }, (_, i) => (
        <Skeleton key={i} className="h-9 w-full" />
      ))}
    </div>
  )
}
