import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowUpRight, Info } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { leadsApi } from '@/lib/api-leads'
import { formatClock, formatHoursMins } from '@/lib/format'
import { LEAD_STATUS_LABELS } from '@/lib/labels'
import type { LeadDetail } from '@/lib/types-leads'

/** Lead Details header (PRD §6.4): who, owner, four stat cards, assignee and status. */
export function LeadHeader({ lead }: { lead: LeadDetail }) {
  const qc = useQueryClient()
  const update = useMutation({
    mutationFn: (body: { status?: string; assignee?: string }) => leadsApi.update(lead.id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['lead', lead.id] })
      qc.invalidateQueries({ queryKey: ['leads'] })
      qc.invalidateQueries({ queryKey: ['lead-kpis'] })
    },
  })

  const s = lead.stats
  const talk = s.talk_listen_agent_pct
  const duration = s.total_duration_s >= 3600 ? formatHoursMins(s.total_duration_s) : formatClock(s.total_duration_s)

  return (
    <header className="mb-6 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <span
            aria-hidden
            className="grid size-12 shrink-0 place-items-center rounded-full bg-ai-soft text-lg font-semibold text-ai"
          >
            {lead.name.replace(/^\+/, '').charAt(0).toUpperCase()}
          </span>
          <div className="min-w-0">
            <h2 className="flex items-center gap-1 text-2xl font-semibold tracking-tight">
              <span className="truncate">{lead.name}</span>
              <Link to={`/leads/${lead.id}?tab=conversations`} aria-label="Open conversations">
                <ArrowUpRight className="size-5 text-muted-foreground" />
              </Link>
            </h2>
            <p className="flex flex-wrap gap-x-3 text-muted-foreground">
              {lead.has_name && lead.phone && <span className="font-mono">{lead.phone}</span>}
              {lead.owner && (
                <span>
                  Owner: <span className="text-foreground">{lead.owner}</span>
                </span>
              )}
            </p>
          </div>
        </div>

        <div className="flex w-full flex-wrap items-end gap-3 sm:w-auto">
          <div className="grid flex-1 gap-1 sm:w-48 sm:flex-none">
            <Label htmlFor="lead-assignee">Assignee</Label>
            <Input
              key={lead.assignee}
              id="lead-assignee"
              defaultValue={lead.assignee}
              placeholder="Unassigned"
              className="bg-surface"
              onBlur={(e) => {
                const value = e.target.value.trim()
                if (value !== lead.assignee) update.mutate({ assignee: value })
              }}
              onKeyDown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
            />
          </div>
          <div className="grid flex-1 gap-1 sm:flex-none">
            <Label htmlFor="lead-status">Status</Label>
            <Select value={lead.status} onValueChange={(status) => update.mutate({ status })}>
              <SelectTrigger id="lead-status" className="w-full bg-surface sm:w-48">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {lead.statuses.map((st) => (
                  <SelectItem key={st} value={st}>
                    {LEAD_STATUS_LABELS[st] ?? st}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>
      {update.isError && (
        <p role="alert" className="rounded-lg bg-negative-soft px-3 py-2 text-negative">
          {update.error.message}
        </p>
      )}

      <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Total Conversation Duration" value={duration} />
        <Stat
          label={
            <span className="inline-flex items-center gap-1">
              Talk-to-Listen Ratio
              <Tooltip>
                <TooltipTrigger asChild>
                  <button type="button" aria-label="What is the talk-to-listen ratio?">
                    <Info className="size-3.5" />
                  </button>
                </TooltipTrigger>
                <TooltipContent>Agent talk time : customer talk time, averaged over this lead's calls.</TooltipContent>
              </Tooltip>
            </span>
          }
          value={talk == null ? '—' : `${talk}:${100 - talk}`}
        />
        <Stat label="Intent Score" value={s.intent_score == null ? '—' : `${s.intent_score}/100`} />
        <Stat
          label="Avg. Call Quality Score"
          value={s.avg_quality_pct == null ? '—' : `${Math.round(s.avg_quality_pct)}%`}
        />
      </dl>
    </header>
  )
}

function Stat({ label, value }: { label: ReactNode; value: string }) {
  return (
    <div className="rounded-xl border bg-surface p-4">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="num mt-1 text-xl font-semibold">{value}</dd>
    </div>
  )
}
