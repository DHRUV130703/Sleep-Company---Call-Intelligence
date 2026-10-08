import { ArrowUpRight, Loader2 } from 'lucide-react'
import { Link } from 'react-router'
import { Checkbox } from '@/components/ui/checkbox'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import type { LeadListItem } from '@/lib/types-leads'
import type { LeadColumn } from './lead-columns'

interface Props {
  rows: LeadListItem[]
  columns: LeadColumn[]
  selected: Record<number, LeadListItem>
  onToggle: (row: LeadListItem, checked: boolean) => void
  onTogglePage: (checked: boolean) => void
}

/** The leads table. Name and the select box are always shown; other columns come from the chooser. */
export function LeadsTable({ rows, columns, selected, onToggle, onTogglePage }: Props) {
  const pickedOnPage = rows.filter((r) => selected[r.id]).length
  const allChecked = rows.length > 0 && pickedOnPage === rows.length
  return (
    <Table>
      <TableHeader className="bg-surface-sunken">
        <TableRow>
          <TableHead className="w-10">
            <Checkbox
              aria-label="Select all leads on this page"
              checked={allChecked ? true : pickedOnPage > 0 ? 'indeterminate' : false}
              onCheckedChange={(c) => onTogglePage(c === true)}
            />
          </TableHead>
          <TableHead>Name</TableHead>
          {columns.map((c) => (
            <TableHead key={c.id}>{c.label}</TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r) => (
          <TableRow key={r.id} data-state={selected[r.id] ? 'selected' : undefined}>
            <TableCell>
              <Checkbox
                aria-label={`Select ${r.name}`}
                checked={Boolean(selected[r.id])}
                onCheckedChange={(c) => onToggle(r, c === true)}
              />
            </TableCell>
            <TableCell>
              <NameCell row={r} />
            </TableCell>
            {columns.map((c) => (
              <TableCell key={c.id}>{c.cell(r)}</TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

function NameCell({ row }: { row: LeadListItem }) {
  return (
    <div className="min-w-36">
      <div className="flex items-center gap-2">
        <Link to={`/leads/${row.id}`} className="inline-flex items-center gap-0.5 font-medium hover:underline">
          {row.name}
          <ArrowUpRight className="size-3.5 text-muted-foreground" aria-hidden />
        </Link>
        {row.processing && (
          <span className="inline-flex items-center gap-1 rounded-full bg-ai-soft px-1.5 py-0.5 text-[11px] text-ai">
            <Loader2 className="size-3 animate-spin" aria-hidden />
            Processing
          </span>
        )}
      </div>
      {row.has_name && row.phone && <div className="font-mono text-xs text-muted-foreground">{row.phone}</div>}
    </div>
  )
}
