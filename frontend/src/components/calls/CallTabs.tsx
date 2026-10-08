// Right-hand panel of the call screen: Summary · Action insights · Scorecard · Key moments · Metrics.

import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Table, TableBody, TableCell, TableRow } from '@/components/ui/table'
import { formatClock, formatDay, humanize } from '@/lib/format'
import type { CallAnalysis, CallMetrics, KeyMoment } from '@/lib/types-calls'
import { cn } from '@/lib/utils'
import { ActionInsightsTab } from './ActionInsightsTab'
import { EvidenceQuote } from './EvidenceQuote'
import { MOMENT_TONE, TONE_BG } from './moments'
import { ScorecardTab } from './ScorecardTab'

interface Props {
  analysis: CallAnalysis | null
  metrics: CallMetrics | null
  metricLabels: Record<string, string>
  onSeek: (seconds: number) => void
}

export function CallTabs({ analysis, metrics, metricLabels, onSeek }: Props) {
  return (
    <Tabs defaultValue="summary" className="rounded-xl border bg-surface p-3">
      <TabsList className="max-w-full justify-start overflow-x-auto">
        <TabsTrigger value="summary">Summary</TabsTrigger>
        <TabsTrigger value="actions">Action insights</TabsTrigger>
        <TabsTrigger value="scorecard">Scorecard</TabsTrigger>
        <TabsTrigger value="moments">Key moments</TabsTrigger>
        <TabsTrigger value="metrics">Metrics</TabsTrigger>
      </TabsList>
      <div className="px-1 pt-2">
        <TabsContent value="summary">
          {analysis ? <SummaryTab analysis={analysis} /> : <NotAnalysed />}
        </TabsContent>
        <TabsContent value="actions">
          {analysis ? <ActionInsightsTab analysis={analysis} onSeek={onSeek} /> : <NotAnalysed />}
        </TabsContent>
        <TabsContent value="scorecard">
          {analysis ? <ScorecardTab analysis={analysis} onSeek={onSeek} /> : <NotAnalysed />}
        </TabsContent>
        <TabsContent value="moments">
          {analysis ? <KeyMomentsTab moments={analysis.key_moments} onSeek={onSeek} /> : <NotAnalysed />}
        </TabsContent>
        <TabsContent value="metrics">
          <MetricsTab metrics={metrics} labels={metricLabels} />
        </TabsContent>
      </div>
    </Tabs>
  )
}

function NotAnalysed() {
  return <p className="py-4 text-muted-foreground">This call hasn't been analysed yet.</p>
}

function SummaryTab({ analysis }: { analysis: CallAnalysis }) {
  const { summary, outcome } = analysis
  return (
    <div className="space-y-5">
      {summary.one_liner && <p className="font-medium">{summary.one_liner}</p>}
      {summary.bullets.length > 0 && (
        <ul className="list-disc space-y-1 pl-5">
          {summary.bullets.map((b, i) => (
            <li key={i}>{b}</li>
          ))}
        </ul>
      )}
      {outcome.next_step && (
        <p>
          <span className="text-muted-foreground">Agreed next step: </span>
          {outcome.next_step}
          {outcome.next_step_due && <span className="num text-muted-foreground"> · due {formatDay(outcome.next_step_due)}</span>}
        </p>
      )}

      <p className="text-sm text-muted-foreground">
        What to pitch and what to do next are in <span className="font-medium">Action insights</span>.
      </p>
    </div>
  )
}

function KeyMomentsTab({ moments, onSeek }: { moments: KeyMoment[]; onSeek: (t: number) => void }) {
  if (moments.length === 0) return <p className="py-4 text-muted-foreground">No key moments in this call.</p>
  const sorted = [...moments].sort((a, b) => a.t - b.t)
  return (
    <ol className="space-y-2">
      {sorted.map((m, i) => {
        const tone = MOMENT_TONE[m.type] ?? 'muted'
        const canSeek = m.t >= 0
        return (
          <li key={i} className="rounded-lg border p-3">
            <button
              type="button"
              disabled={!canSeek}
              onClick={() => onSeek(m.t)}
              className="flex w-full items-center gap-2 rounded-md text-left outline-none focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-default"
            >
              <span className={cn('size-2.5 shrink-0 rounded-full', TONE_BG[tone])} aria-hidden />
              <span className="num w-12 shrink-0 font-mono text-xs text-muted-foreground">
                {canSeek ? formatClock(m.t) : '—'}
              </span>
              <span className="min-w-0 flex-1 font-medium">{m.label || humanize(m.type)}</span>
              <span className="shrink-0 rounded-full bg-surface-sunken px-2 py-0.5 text-xs text-muted-foreground">
                {humanize(m.type)}
              </span>
            </button>
            <EvidenceQuote quote={m.quote} t={m.t} verified={m.verified} onSeek={onSeek} className="mt-2" />
          </li>
        )
      })}
    </ol>
  )
}

function formatMetric(key: string, value: number | boolean): string {
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (key === 'duration_s') return formatClock(value)
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

function MetricsTab({ metrics, labels }: { metrics: CallMetrics | null; labels: Record<string, string> }) {
  if (!metrics) return <p className="py-4 text-muted-foreground">Metrics appear once the transcript is ready.</p>
  const agent = metrics.talk_listen_agent_pct
  const customer = metrics.talk_listen_customer_pct
  return (
    <div className="space-y-2">
      <Table>
        <TableBody>
          {typeof agent === 'number' && typeof customer === 'number' && (
            <TableRow>
              <TableCell className="whitespace-normal">Talk-to-listen (agent : customer)</TableCell>
              <TableCell className="num text-right font-medium">
                {agent}:{customer}
              </TableCell>
            </TableRow>
          )}
          {Object.entries(labels)
            .filter(([key]) => key !== 'talk_listen_agent_pct' && metrics[key] !== undefined)
            .map(([key, label]) => (
              <TableRow key={key}>
                <TableCell className="whitespace-normal">{label}</TableCell>
                <TableCell className="num text-right font-medium">{formatMetric(key, metrics[key])}</TableCell>
              </TableRow>
            ))}
        </TableBody>
      </Table>
      <p className="text-xs text-muted-foreground">Counted directly from who said what, not judged by the model.</p>
    </div>
  )
}
