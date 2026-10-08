import { Layers } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { AgentChip } from '@/components/AgentChip'
import { IntentPill } from '@/components/IntentPill'
import { formatDateTime } from '@/lib/format'
import { INTENT_LABELS, LEAD_STATUS_LABELS } from '@/lib/labels'
import { formatShortDate, initials } from '@/lib/leads-format'
import type { LeadListItem } from '@/lib/types-leads'
import { cn } from '@/lib/utils'

// The optional columns of the leads table (the column chooser picks from these) and the CSV export.

/** One optional column: how it looks in the table and what goes in the CSV export. */
export interface LeadColumn {
  id: string
  label: string
  cell: (row: LeadListItem) => ReactNode
  csv: (row: LeadListItem) => string
}

const conversationsText = (n: number) => `${n} ${n === 1 ? 'Conversation' : 'Conversations'}`

const nextTaskText = (row: LeadListItem) => {
  const t = row.next_task
  if (!t) return ''
  return t.due_date ? `${formatShortDate(t.due_date)} – ${t.title}` : t.title
}

const STATUS_STYLE: Record<string, string> = {
  won: 'bg-positive-soft text-positive',
  lost: 'bg-negative-soft text-negative',
  in_progress: 'bg-surface-sunken',
}

export const LEAD_COLUMNS: LeadColumn[] = [
  {
    id: 'conversations',
    label: 'Conversations',
    // A lead is one phone number; several recordings of that number stack under it.
    cell: (r) => (
      <Link
        to={`/leads/${r.id}?tab=conversations`}
        className="inline-flex items-center gap-1 whitespace-nowrap text-ai hover:underline"
      >
        {r.conversations > 1 && <Layers className="size-3.5" aria-hidden />}
        {conversationsText(r.conversations)}
      </Link>
    ),
    csv: (r) => String(r.conversations),
  },
  {
    id: 'last_conversation',
    label: 'Last Conversation',
    cell: (r) => <span className="num whitespace-nowrap">{r.last_call_at ? formatDateTime(r.last_call_at) : '—'}</span>,
    csv: (r) => (r.last_call_at ? formatDateTime(r.last_call_at) : ''),
  },
  {
    id: 'next_task',
    label: 'Next Task Due Date',
    cell: (r) =>
      r.next_task ? (
        <span className="line-clamp-2 min-w-48">
          {r.next_task.due_date && <span className="num font-medium">{formatShortDate(r.next_task.due_date)} – </span>}
          {r.next_task.title}
        </span>
      ) : (
        <span className="text-muted-foreground">—</span>
      ),
    csv: nextTaskText,
  },
  {
    id: 'intent',
    label: 'Intent',
    cell: (r) => <IntentPill bucket={r.intent_bucket} score={r.intent_score} short />,
    csv: (r) =>
      r.intent_bucket
        ? `${INTENT_LABELS[r.intent_bucket] ?? r.intent_bucket}${r.intent_score != null ? ` ${r.intent_score}/100` : ''}`
        : '',
  },
  {
    id: 'agent_type',
    label: 'Agent type',
    cell: (r) => (
      <span className="flex flex-wrap gap-1">
        {r.agent_types.map((t) => (
          <AgentChip key={t} type={t} className="whitespace-nowrap" />
        ))}
      </span>
    ),
    csv: (r) => r.agent_types.map((t) => (t === 'ai' ? 'AI' : 'Human')).join(' + '),
  },
  {
    id: 'owner',
    label: 'Conversation owner',
    cell: (r) =>
      r.owner ? (
        <span className="flex items-center gap-2">
          <span
            aria-hidden
            className="grid size-7 shrink-0 place-items-center rounded-full bg-surface-sunken text-xs font-medium"
          >
            {initials(r.owner)}
          </span>
          <span className="min-w-32">{r.owner}</span>
        </span>
      ) : (
        <span className="text-muted-foreground">—</span>
      ),
    csv: (r) => r.owner,
  },
  {
    id: 'status',
    label: 'Status',
    cell: (r) => (
      <span className={cn('whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium', STATUS_STYLE[r.status_category])}>
        {LEAD_STATUS_LABELS[r.status] ?? r.status}
      </span>
    ),
    csv: (r) => LEAD_STATUS_LABELS[r.status] ?? r.status,
  },
]

/** CSV rows for the export: name and phone, then whichever columns are visible. */
export function leadsCsv(rows: LeadListItem[], columns: LeadColumn[]): { header: string[]; body: string[][] } {
  return {
    header: ['Name', 'Phone', ...columns.map((c) => c.label)],
    body: rows.map((r) => [r.has_name ? r.name : '', r.phone, ...columns.map((c) => c.csv(r))]),
  }
}
