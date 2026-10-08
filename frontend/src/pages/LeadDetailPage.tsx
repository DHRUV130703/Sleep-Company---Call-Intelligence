import { useQuery } from '@tanstack/react-query'
import { UserRound } from 'lucide-react'
import { Link, useParams, useSearchParams } from 'react-router'
import { EmptyState } from '@/components/EmptyState'
import { ActionsTab } from '@/components/leads/ActionsTab'
import { ConversationsTab } from '@/components/leads/ConversationsTab'
import { InsightsPanel } from '@/components/leads/InsightsPanel'
import { LeadHeader } from '@/components/leads/LeadHeader'
import { NotesTab } from '@/components/leads/NotesTab'
import { PathToConversion } from '@/components/leads/PathToConversion'
import { SummaryTab } from '@/components/leads/SummaryTab'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ApiError } from '@/lib/api'
import { leadsApi } from '@/lib/api-leads'

const TABS = ['insights', 'conversations', 'summary', 'actions', 'notes'] as const

/** Lead Details (PRD §6.4). The selected tab lives in `?tab=` so it can be linked to. */
export default function LeadDetailPage() {
  const leadId = Number(useParams().leadId)
  const [params, setParams] = useSearchParams()
  const tab = TABS.find((t) => t === params.get('tab')) ?? 'insights'

  const lead = useQuery({
    queryKey: ['lead', leadId],
    queryFn: () => leadsApi.detail(leadId),
    enabled: Number.isFinite(leadId),
    // Keep refreshing while a recording of this lead is still being processed.
    refetchInterval: (q) =>
      q.state.data?.calls.some((c) => c.status === 'queued' || c.status === 'running') ? 5000 : false,
  })

  const setTab = (value: string) =>
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        if (value === 'insights') next.delete('tab')
        else next.set('tab', value)
        return next
      },
      { replace: true },
    )

  if (!Number.isFinite(leadId) || (lead.isError && lead.error instanceof ApiError && lead.error.status === 404)) {
    return (
      <EmptyState
        icon={UserRound}
        title="Lead not found"
        description="It may have been removed, or the link is wrong."
        action={
          <Button variant="outline" asChild>
            <Link to="/leads">All conversations</Link>
          </Button>
        }
      />
    )
  }
  if (lead.isError) {
    return (
      <p role="alert" className="rounded-lg bg-negative-soft px-3 py-2 text-negative">
        {lead.error.message}
      </p>
    )
  }
  if (lead.isPending) return <DetailSkeleton />

  const d = lead.data
  const openActions = d.actions.filter((a) => !a.done).length
  return (
    <>
      <LeadHeader lead={d} />
      <Tabs value={tab} onValueChange={setTab} className="gap-4">
        <div className="-mx-4 overflow-x-auto px-4 md:mx-0 md:px-0">
          <TabsList variant="line" className="border-b">
            <TabsTrigger value="insights">Insights</TabsTrigger>
            <TabsTrigger value="conversations">
              Conversations <Count n={d.calls.length} />
            </TabsTrigger>
            <TabsTrigger value="summary">Summary</TabsTrigger>
            <TabsTrigger value="actions">
              Actions <Count n={openActions} />
            </TabsTrigger>
            <TabsTrigger value="notes">
              Notes <Count n={d.notes.length} />
            </TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="insights">
          <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,65fr)_minmax(0,35fr)]">
            <InsightsPanel insights={d.insights} />
            <PathToConversion path={d.path} />
          </div>
        </TabsContent>
        <TabsContent value="conversations">
          <ConversationsTab calls={d.calls} />
        </TabsContent>
        <TabsContent value="summary">
          <SummaryTab calls={d.calls} />
        </TabsContent>
        <TabsContent value="actions">
          <ActionsTab leadId={d.id} actions={d.actions} />
        </TabsContent>
        <TabsContent value="notes">
          <NotesTab leadId={d.id} notes={d.notes} />
        </TabsContent>
      </Tabs>
    </>
  )
}

function Count({ n }: { n: number }) {
  if (n === 0) return null
  return <span className="num rounded-full bg-surface-sunken px-1.5 text-xs">{n}</span>
}

function DetailSkeleton() {
  return (
    <div className="space-y-4" aria-busy="true">
      <div className="flex items-center gap-3">
        <Skeleton className="size-12 rounded-full" />
        <Skeleton className="h-8 w-56" />
      </div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <Skeleton key={i} className="h-20 rounded-xl" />
        ))}
      </div>
      <Skeleton className="h-8 w-80" />
      <div className="grid gap-4 lg:grid-cols-[65fr_35fr]">
        <Skeleton className="h-96 rounded-xl" />
        <Skeleton className="h-96 rounded-xl" />
      </div>
    </div>
  )
}
