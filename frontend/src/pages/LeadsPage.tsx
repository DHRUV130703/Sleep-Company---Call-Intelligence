import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ChevronDown, ChevronLeft, ChevronRight, Download, MessagesSquare } from 'lucide-react'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { EmptyState } from '@/components/EmptyState'
import { PageHeader } from '@/components/PageHeader'
import { FilterBar } from '@/components/leads/FilterBar'
import { KpiHeader } from '@/components/leads/KpiHeader'
import { LEAD_COLUMNS, leadsCsv } from '@/components/leads/lead-columns'
import { LeadsTable } from '@/components/leads/LeadsTable'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { filtersFromParams, leadsApi } from '@/lib/api-leads'
import { downloadText, isoDay, toCsv } from '@/lib/leads-format'
import { readPref, writePref } from '@/lib/storage'
import type { LeadListItem } from '@/lib/types-leads'

const PAGE_SIZE = 25
const COLUMNS_PREF = 'leads.columns'

const SORTS = [
  { value: 'last_call', label: 'Last conversation' },
  { value: 'intent', label: 'Intent score' },
  { value: 'name', label: 'Name' },
]

/** All Conversations (PRD §6.3): filters, KPIs, intent buckets and the leads table. */
export default function LeadsPage() {
  const [params, setParams] = useSearchParams()
  const filters = filtersFromParams(params)
  const sort = params.get('sort') || 'last_call'
  const page = Math.max(1, Number(params.get('page')) || 1)

  const listParams = { ...filters, sort, page, page_size: PAGE_SIZE }
  const leads = useQuery({
    queryKey: ['leads', listParams],
    queryFn: () => leadsApi.list(listParams),
    placeholderData: keepPreviousData,
    // While any call is still being analysed, refresh so the spinner badges clear by themselves.
    refetchInterval: (q) => (q.state.data?.items.some((r) => r.processing) ? 5000 : false),
  })

  const [visibleIds, setVisibleIds] = useState<string[]>(() =>
    readPref(COLUMNS_PREF, LEAD_COLUMNS.map((c) => c.id)),
  )
  const columns = LEAD_COLUMNS.filter((c) => visibleIds.includes(c.id))
  const toggleColumn = (id: string, on: boolean) => {
    const next = on ? [...visibleIds, id] : visibleIds.filter((v) => v !== id)
    setVisibleIds(next)
    writePref(COLUMNS_PREF, next)
  }

  const [selected, setSelected] = useState<Record<number, LeadListItem>>({})
  const selectedRows = Object.values(selected)
  const toggleRow = (row: LeadListItem, on: boolean) =>
    setSelected((s) => {
      const next = { ...s }
      if (on) next[row.id] = row
      else delete next[row.id]
      return next
    })
  const togglePage = (on: boolean) =>
    setSelected((s) => {
      const next = { ...s }
      for (const r of leads.data?.items ?? []) {
        if (on) next[r.id] = r
        else delete next[r.id]
      }
      return next
    })
  const exportCsv = () => {
    const { header, body } = leadsCsv(selectedRows, columns)
    downloadText(`leads-${isoDay()}.csv`, toCsv(header, body))
  }

  const setParam = (key: string, value: string) =>
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        if (value) next.set(key, value)
        else next.delete(key)
        if (key !== 'page') next.delete('page')
        return next
      },
      { replace: key !== 'page' },
    )

  const total = leads.data?.total ?? 0
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const hasFilters = Object.keys(filters).length > 0

  return (
    <>
      <PageHeader
        title="All Conversations"
        description="One row per lead. Calls from the same number are grouped together."
      />
      <FilterBar />
      <KpiHeader
        filters={filters}
        selectedBucket={filters.intent_bucket ?? ''}
        onSelectBucket={(b) => setParam('intent_bucket', b)}
      />

      <section aria-labelledby="leads-title" className="rounded-xl border bg-surface">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b px-4 py-3">
          <h3 id="leads-title" className="font-semibold">
            Leads <span className="num font-normal text-muted-foreground">({total.toLocaleString()})</span>
          </h3>
          <div className="flex flex-wrap items-center gap-2">
            <Select value={sort} onValueChange={(v) => setParam('sort', v === 'last_call' ? '' : v)}>
              <SelectTrigger aria-label="Sort leads by" size="sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {SORTS.map((s) => (
                  <SelectItem key={s.value} value={s.value}>
                    Sort: {s.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" aria-label="Choose columns">
                  <span className="num">{columns.length + 1}</span> Selected
                  <ChevronDown />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel>Columns</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuCheckboxItem checked disabled>
                  Name
                </DropdownMenuCheckboxItem>
                {LEAD_COLUMNS.map((c) => (
                  <DropdownMenuCheckboxItem
                    key={c.id}
                    checked={visibleIds.includes(c.id)}
                    onCheckedChange={(on) => toggleColumn(c.id, on)}
                    onSelect={(e) => e.preventDefault()}
                  >
                    {c.label}
                  </DropdownMenuCheckboxItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
            <Button size="sm" onClick={exportCsv} disabled={selectedRows.length === 0}>
              <Download />
              Export CSV{selectedRows.length > 0 && <span className="num"> ({selectedRows.length})</span>}
            </Button>
          </div>
        </div>

        {leads.isPending && <TableSkeleton />}
        {leads.isError && (
          <p role="alert" className="m-4 rounded-lg bg-negative-soft px-3 py-2 text-negative">
            {leads.error.message}
          </p>
        )}
        {leads.data && leads.data.items.length === 0 && (
          <div className="p-4">
            {hasFilters ? (
              <EmptyState
                icon={MessagesSquare}
                title="No leads match these filters"
                description="Try a wider date range, or reset the filters."
                action={
                  <Button variant="outline" onClick={() => setParams(new URLSearchParams())}>
                    Reset all filters
                  </Button>
                }
              />
            ) : (
              <EmptyState
                icon={MessagesSquare}
                title="No conversations yet"
                description="Once calls are analysed, leads appear here with their intent score, last conversation and next task."
                action={
                  <Button asChild>
                    <Link to="/upload">Upload recordings →</Link>
                  </Button>
                }
              />
            )}
          </div>
        )}
        {leads.data && leads.data.items.length > 0 && (
          <>
            <LeadsTable
              rows={leads.data.items}
              columns={columns}
              selected={selected}
              onToggle={toggleRow}
              onTogglePage={togglePage}
            />
            <nav aria-label="Pagination" className="flex flex-wrap items-center justify-between gap-2 border-t px-4 py-3">
              <span className="num text-muted-foreground">
                {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} of {total.toLocaleString()}
              </span>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setParam('page', String(page - 1))}
                >
                  <ChevronLeft /> Previous
                </Button>
                <span className="num text-sm">
                  Page {page} of {pageCount}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= pageCount}
                  onClick={() => setParam('page', String(page + 1))}
                >
                  Next <ChevronRight />
                </Button>
              </div>
            </nav>
          </>
        )}
      </section>
    </>
  )
}

function TableSkeleton() {
  return (
    <div className="space-y-2 p-4" aria-busy="true">
      {Array.from({ length: 8 }, (_, i) => (
        <Skeleton key={i} className="h-11 w-full" />
      ))}
    </div>
  )
}
