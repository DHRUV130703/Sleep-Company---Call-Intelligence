import { useState } from 'react'
import { Table2, ChartBarBig } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { CompareResult, DimensionRow, Side } from '@/lib/types-compare'
import { cn } from '@/lib/utils'
import { CompareSection, SideLabel } from './CompareSection'
import { formatValue } from './format-value'

const MAX_SCORE = 5

/** D. Review scores per scorecard dimension. AI bars grow left (blue), Human bars grow right (orange). */
export function DivergingBars({ data }: { data: CompareResult }) {
  const [asTable, setAsTable] = useState(false)
  const rows = data.dimensions

  return (
    <CompareSection
      id="scores"
      title="Review scores"
      caption="Average per dimension, 1 (poor) to 5 (excellent)."
      action={
        <Button variant="outline" size="sm" aria-pressed={asTable} onClick={() => setAsTable((v) => !v)}>
          {asTable ? <ChartBarBig className="size-3.5" aria-hidden /> : <Table2 className="size-3.5" aria-hidden />}
          {asTable ? 'Show as a chart' : 'Show as a table'}
        </Button>
      }
    >
      {rows.length === 0 ? (
        <p className="text-muted-foreground">No scorecard dimensions are configured.</p>
      ) : asTable ? (
        <ScoresTable rows={rows} />
      ) : (
        <figure>
          <div className="mb-2 grid grid-cols-[1fr_6.5rem_1fr] text-xs sm:grid-cols-[1fr_11rem_1fr]" aria-hidden>
            <SideLabel side="ai" className="justify-self-end pr-1" />
            <span />
            <SideLabel side="human" className="pl-1" />
          </div>
          <ul className="space-y-1.5">
            {rows.map((r) => (
              <BarRow key={r.key} row={r} />
            ))}
          </ul>
          <figcaption className="mt-3 flex flex-wrap justify-between gap-x-4 gap-y-1 border-t pt-2 text-xs text-muted-foreground">
            <span>
              <span className="text-ai">◂ AI scores higher</span> · <span className="text-human">Human scores higher ▸</span>
            </span>
            <span>Bars run from 0 at the centre to 5 at the edge.</span>
          </figcaption>
        </figure>
      )}
    </CompareSection>
  )
}

function BarRow({ row }: { row: DimensionRow }) {
  return (
    <li
      className="grid grid-cols-[1fr_6.5rem_1fr] items-center sm:grid-cols-[1fr_11rem_1fr]"
      aria-label={`${row.label}: AI ${formatValue(row.ai)}, Human ${formatValue(row.human)} out of 5`}
    >
      <HalfBar value={row.ai} side="ai" />
      <span className="px-2 text-center text-xs leading-tight sm:text-[13px]" aria-hidden>
        {row.label}
      </span>
      <HalfBar value={row.human} side="human" />
    </li>
  )
}

/** One half of a diverging row. Padding on the outer edge leaves room for the value label at 5/5. */
function HalfBar({ value, side }: { value: number | null; side: Side }) {
  const isAi = side === 'ai'
  const pct = value === null ? 0 : (Math.min(value, MAX_SCORE) / MAX_SCORE) * 100
  const labelPos = `calc(${pct}% + 4px)`
  return (
    <div className={cn('h-6', isAi ? 'pl-8' : 'pr-8')} aria-hidden>
      <div className={cn('relative h-full', isAi ? 'border-r' : 'border-l')}>
        <div
          className={cn(
            'absolute top-1 bottom-1 transition-[width] duration-200 ease-out motion-reduce:transition-none',
            isAi ? 'right-0 rounded-l bg-ai' : 'left-0 rounded-r bg-human',
          )}
          style={{ width: `${pct}%` }}
        />
        <span
          className={cn('num absolute top-1/2 -translate-y-1/2 text-xs font-medium', isAi ? 'text-ai' : 'text-human')}
          style={isAi ? { right: labelPos } : { left: labelPos }}
        >
          {formatValue(value)}
        </span>
      </div>
    </div>
  )
}

function ScoresTable({ rows }: { rows: DimensionRow[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left">
        <caption className="sr-only">Average review score per dimension, out of 5</caption>
        <thead>
          <tr className="border-b text-xs text-muted-foreground">
            <th scope="col" className="py-2 pr-3 font-medium">Dimension</th>
            <th scope="col" className="px-3 py-2 text-right"><SideLabel side="ai" className="text-xs" /></th>
            <th scope="col" className="px-3 py-2 text-right"><SideLabel side="human" className="text-xs" /></th>
            <th scope="col" className="py-2 pl-3 text-right font-medium">Higher</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key} className="border-b last:border-0">
              <th scope="row" className="py-2 pr-3 font-normal">{r.label}</th>
              <td className="num px-3 py-2 text-right">
                {formatValue(r.ai)} <span className="text-xs text-muted-foreground">(n={r.ai_n})</span>
              </td>
              <td className="num px-3 py-2 text-right">
                {formatValue(r.human)} <span className="text-xs text-muted-foreground">(n={r.human_n})</span>
              </td>
              <td className="num py-2 pl-3 text-right">{higher(r)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function higher(r: DimensionRow) {
  if (r.ai === null || r.human === null) return <span className="text-muted-foreground">—</span>
  const diff = Math.round((r.human - r.ai) * 10) / 10
  if (diff === 0) return <span className="text-muted-foreground">Equal</span>
  return diff > 0 ? (
    <span className="text-human">Human +{diff}</span>
  ) : (
    <span className="text-ai">AI +{-diff}</span>
  )
}
