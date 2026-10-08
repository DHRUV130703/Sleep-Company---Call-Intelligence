import { useQuery } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { ChevronDown, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { compareApi } from '@/lib/api-compare'
import type { BatchOption, CompareScope } from '@/lib/types-compare'

interface Props {
  scope: CompareScope
  onChange: (scope: CompareScope) => void
}

const ALL_CAMPAIGNS = '__all__'

/** Which calls go into the comparison: batches, campaign, date range, "only comparable calls". */
export function ScopePicker({ scope, onChange }: Props) {
  const options = useQuery({ queryKey: ['compare-options'], queryFn: compareApi.options })
  const batches = options.data?.batches ?? []
  const campaigns = options.data?.campaigns ?? []
  const isFiltered =
    scope.batchIds.length > 0 || !!scope.campaign || !!scope.dateFrom || !!scope.dateTo || scope.comparableOnly

  const set = (patch: Partial<CompareScope>) => onChange({ ...scope, ...patch })

  return (
    <div
      role="group"
      aria-label="Which calls to compare"
      className="mb-6 flex flex-wrap items-end gap-x-4 gap-y-3 rounded-xl border bg-surface px-4 py-3"
    >
      <Field label="Batches" htmlFor="scope-batches">
        <BatchPicker
          batches={batches}
          selected={scope.batchIds}
          loading={options.isPending}
          onChange={(batchIds) => set({ batchIds })}
        />
      </Field>

      <Field label="Campaign" htmlFor="scope-campaign">
        <Select
          value={scope.campaign || ALL_CAMPAIGNS}
          onValueChange={(v) => set({ campaign: v === ALL_CAMPAIGNS ? '' : v })}
        >
          <SelectTrigger id="scope-campaign" className="w-full sm:w-56">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_CAMPAIGNS}>All campaigns</SelectItem>
            {campaigns.map((c) => (
              <SelectItem key={c} value={c}>
                {c}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>

      <Field label="From" htmlFor="scope-from">
        <Input
          id="scope-from"
          type="date"
          className="w-full sm:w-40"
          value={scope.dateFrom}
          max={scope.dateTo || undefined}
          onChange={(e) => set({ dateFrom: e.target.value })}
        />
      </Field>
      <Field label="To" htmlFor="scope-to">
        <Input
          id="scope-to"
          type="date"
          className="w-full sm:w-40"
          value={scope.dateTo}
          min={scope.dateFrom || undefined}
          onChange={(e) => set({ dateTo: e.target.value })}
        />
      </Field>

      <div className="flex min-h-8 items-center gap-2">
        <Checkbox
          id="scope-comparable"
          checked={scope.comparableOnly}
          onCheckedChange={(v) => set({ comparableOnly: v === true })}
          aria-describedby="scope-comparable-hint"
        />
        <div>
          <Label htmlFor="scope-comparable">Only comparable calls</Label>
          <p id="scope-comparable-hint" className="text-xs text-muted-foreground">
            Connected, analysed, 20 s or longer
          </p>
        </div>
      </div>

      {isFiltered && (
        <Button
          variant="ghost"
          size="sm"
          className="ml-auto"
          onClick={() => onChange({ batchIds: [], campaign: '', dateFrom: '', dateTo: '', comparableOnly: false })}
        >
          <X className="size-3.5" aria-hidden />
          Clear filters
        </Button>
      )}
    </div>
  )
}

function Field({ label, htmlFor, children }: { label: string; htmlFor: string; children: ReactNode }) {
  return (
    <div className="flex w-full flex-col gap-1 sm:w-auto">
      <Label htmlFor={htmlFor} className="text-xs text-muted-foreground">
        {label}
      </Label>
      {children}
    </div>
  )
}

interface BatchPickerProps {
  batches: BatchOption[]
  selected: number[]
  loading: boolean
  onChange: (ids: number[]) => void
}

function BatchPicker({ batches, selected, loading, onChange }: BatchPickerProps) {
  const summary =
    selected.length === 0
      ? 'All batches'
      : selected.length === 1
        ? (batches.find((b) => b.id === selected[0])?.name ?? '1 batch')
        : `${selected.length} batches`

  const toggle = (id: number, on: boolean) =>
    onChange(on ? [...selected, id].sort((a, b) => a - b) : selected.filter((x) => x !== id))

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button id="scope-batches" variant="outline" className="w-full justify-between font-normal sm:w-56">
          <span className="truncate">{summary}</span>
          <ChevronDown className="size-4 text-muted-foreground" aria-hidden />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-80 max-w-[calc(100vw-2rem)]">
        {loading && <p className="text-muted-foreground">Loading batches…</p>}
        {!loading && batches.length === 0 && <p className="text-muted-foreground">No batches yet.</p>}
        {batches.length > 0 && (
          <ul className="max-h-72 space-y-1 overflow-y-auto" aria-label="Batches">
            {batches.map((b) => {
              const id = `scope-batch-${b.id}`
              return (
                <li key={b.id} className="flex items-start gap-2 rounded-md px-1.5 py-1.5 hover:bg-accent">
                  <Checkbox
                    id={id}
                    className="mt-0.5"
                    checked={selected.includes(b.id)}
                    onCheckedChange={(v) => toggle(b.id, v === true)}
                  />
                  <label htmlFor={id} className="min-w-0 flex-1 cursor-pointer">
                    <span className="block truncate">{b.name}</span>
                    <span className="num text-xs">
                      <span className="text-ai">AI {b.ai}</span>
                      <span className="text-muted-foreground"> · </span>
                      <span className="text-human">Human {b.human}</span>
                    </span>
                  </label>
                </li>
              )
            })}
          </ul>
        )}
        {selected.length > 0 && (
          <Button variant="ghost" size="sm" className="self-start" onClick={() => onChange([])}>
            Use all batches
          </Button>
        )}
      </PopoverContent>
    </Popover>
  )
}
