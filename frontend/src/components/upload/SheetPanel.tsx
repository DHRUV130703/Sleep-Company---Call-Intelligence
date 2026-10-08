import { useMutation, useQuery } from '@tanstack/react-query'
import { CircleCheck, FileSpreadsheet, Layers, Loader2, TriangleAlert } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { Button } from '@/components/ui/button'
import { batchesApi } from '@/lib/api-batches'
import type { AgentMode, SheetCheck, SheetPreview } from '@/lib/types-batches'
import { cn } from '@/lib/utils'

// Which spreadsheet column holds which field (PRD §6.1.2).
const FIELD_LABELS: Record<string, { label: string; required?: boolean }> = {
  recording_url: { label: 'Recording link', required: true },
  lead_phone: { label: 'Lead phone (groups calls into leads)' },
  lead_name: { label: 'Customer name' },
  agent_type: { label: 'Agent type (AI / Human)' },
  call_datetime: { label: 'Call date & time' },
  agent_name: { label: 'Agent / owner' },
  campaign: { label: 'Campaign' },
  external_id: { label: 'Call ID' },
}

export interface SheetState {
  preview: SheetPreview | null
  mapping: Record<string, string | null>
}

interface Props {
  value: SheetState
  mode: AgentMode
  onChange: (v: SheetState) => void
  onCheck: (ok: boolean) => void
}

export function SheetPanel({ value, mode, onChange, onCheck }: Props) {
  const input = useRef<HTMLInputElement>(null)
  const upload = useMutation({
    mutationFn: batchesApi.previewSheet,
    onSuccess: (preview) => onChange({ preview, mapping: preview.mapping }),
  })
  const { preview, mapping } = value

  const check = useQuery({
    queryKey: ['sheet-check', preview?.sheet_id, mapping, mode],
    queryFn: () => batchesApi.checkSheet(preview!.sheet_id, mapping, mode),
    enabled: !!preview && !!mapping.recording_url,
  })
  const ready = !!check.data && check.data.valid > 0 && !check.isFetching
  useEffect(() => onCheck(ready), [ready, onCheck])

  const fields = Object.keys(FIELD_LABELS).filter((f) => f !== 'agent_type' || mode === 'column')
  const mapped = new Set(Object.values(mapping).filter(Boolean))

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-dashed bg-surface px-4 py-4">
        <FileSpreadsheet className="size-6 text-muted-foreground" aria-hidden />
        <div className="min-w-0 flex-1">
          <div className="font-medium">{preview ? preview.filename : 'Excel or CSV with one recording link per row'}</div>
          <div className="text-xs text-muted-foreground">
            {preview
              ? `${preview.total_rows} rows · ${preview.headers.length} columns`
              : '.xlsx, .xls or .csv · columns like Phone Number, Call Recording URL, Agent type…'}
          </div>
        </div>
        <Button variant={preview ? 'outline' : 'default'} onClick={() => input.current?.click()} disabled={upload.isPending}>
          {upload.isPending && <Loader2 className="size-4 animate-spin" />}
          {preview ? 'Choose another file' : 'Choose spreadsheet'}
        </Button>
        <input
          ref={input}
          type="file"
          accept=".xlsx,.xls,.csv"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (f) upload.mutate(f)
            e.target.value = ''
          }}
        />
      </div>
      {upload.isError && <p role="alert" className="text-negative">{upload.error.message}</p>}

      {preview && (
        <>
          <section>
            <h3 className="mb-2 font-medium">Match your columns</h3>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {fields.map((f) => {
                const missing = (FIELD_LABELS[f].required || (f === 'agent_type' && mode === 'column')) && !mapping[f]
                return (
                  <label key={f} className="space-y-1 text-sm">
                    <span className="block text-muted-foreground">
                      {FIELD_LABELS[f].label}
                      {missing && <span className="text-negative"> · required</span>}
                    </span>
                    <select
                      value={mapping[f] ?? ''}
                      onChange={(e) => onChange({ preview, mapping: { ...mapping, [f]: e.target.value || null } })}
                      className={cn('h-9 w-full rounded-md border bg-surface px-2', missing && 'border-negative')}
                    >
                      <option value="">— not in sheet —</option>
                      {preview.headers.map((h) => (
                        <option key={h} value={h}>{h}</option>
                      ))}
                    </select>
                  </label>
                )
              })}
            </div>
          </section>

          <CheckSummary data={check.data} loading={check.isFetching} error={check.error} />

          <section>
            <h3 className="mb-2 font-medium">Preview (first {preview.rows.length} rows)</h3>
            <div className="max-h-80 overflow-auto rounded-xl border bg-surface">
              <table className="w-full text-left text-xs">
                <thead className="sticky top-0 bg-surface-sunken">
                  <tr>
                    <th className="px-3 py-2 font-medium text-muted-foreground">Row</th>
                    {preview.headers.map((h) => (
                      <th key={h} className={cn('px-3 py-2 font-medium', mapped.has(h) ? 'text-foreground' : 'text-muted-foreground')}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {preview.rows.map((row, i) => (
                    <tr key={i}>
                      <td className="num px-3 py-1.5 text-muted-foreground">{i + 2}</td>
                      {preview.headers.map((h) => (
                        <td key={h} className={cn('max-w-72 truncate px-3 py-1.5', !mapped.has(h) && 'text-muted-foreground')} title={row[h]}>
                          {row[h]}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  )
}

function CheckSummary({ data: c, loading, error }: { data?: SheetCheck; loading: boolean; error: Error | null }) {
  if (loading && !c) return <p className="text-muted-foreground">Checking rows…</p>
  if (error) return <p role="alert" className="text-negative">{error.message}</p>
  if (!c) return null
  const ok = c.valid > 0
  return (
    <div className={cn('rounded-xl border px-4 py-3', ok ? 'bg-positive-soft/50' : 'bg-negative-soft')} aria-live="polite">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        {ok ? <CircleCheck className="size-4 text-positive" /> : <TriangleAlert className="size-4 text-negative" />}
        <span className="num font-medium">
          {c.total_rows} rows · {c.valid} valid links
          {c.duplicates > 0 && ` · ${c.duplicates} duplicates removed`}
          {c.problem_count > 0 && ` · ${c.problem_count} with problems`}
        </span>
        <span className="num text-muted-foreground">· AI {c.by_agent_type.ai} · Human {c.by_agent_type.human}</span>
      </div>
      <div className="mt-1 flex items-center gap-1.5 text-sm text-muted-foreground">
        <Layers className="size-4" aria-hidden />
        <span className="num">
          {c.leads} leads
          {c.stacked_phones > 0 &&
            ` — ${c.stacked_phones} phone number${c.stacked_phones > 1 ? 's have' : ' has'} more than one recording; those recordings are stacked under one lead`}
        </span>
      </div>
      {c.problems.length > 0 && (
        <ul className="mt-2 max-h-32 overflow-auto text-sm text-negative">
          {c.problems.slice(0, 20).map((p) => (
            <li key={p.row}>Row {p.row}: {p.message}</li>
          ))}
        </ul>
      )}
    </div>
  )
}
