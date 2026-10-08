import { Loader2, TriangleAlert } from 'lucide-react'
import type { ReactNode } from 'react'
import { formatHoursMins } from '@/lib/format'
import type { CompareResult } from '@/lib/types-compare'
import { CompareSection } from './CompareSection'

/** "55 s" for under a minute, otherwise "1 hour 4 mins". */
function formatAudio(seconds: number): string {
  return seconds < 60 ? `${Math.round(seconds)} s` : formatHoursMins(seconds)
}

/** A. The record counts behind every number on this page, plus the sample-size warning. */
export function RecordsStrip({ data }: { data: CompareResult }) {
  const { ai, human } = data.records
  const inProgress = ai.in_progress + human.in_progress

  return (
    <CompareSection
      id="records"
      title="Records"
      caption="How many calls are behind every number on this page."
    >
      <dl className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Tile label="Total recordings" value={ai.uploaded + human.uploaded} />
        <Tile
          label="AI calls"
          value={<span className="text-ai">{ai.analysed} / {ai.uploaded}</span>}
          note="analysed / uploaded"
        />
        <Tile
          label="Human calls"
          value={<span className="text-human">{human.analysed} / {human.uploaded}</span>}
          note="analysed / uploaded"
        />
        <Tile label="Failed" value={ai.failed + human.failed} note={`AI ${ai.failed} · Human ${human.failed}`} />
        <Tile
          label="Not connected"
          value={ai.not_connected + human.not_connected}
          note={`AI ${ai.not_connected} · Human ${human.not_connected}`}
        />
        <Tile
          label="Total audio"
          value={<span className="text-lg">{formatAudio(ai.audio_seconds + human.audio_seconds)}</span>}
          note={`AI ${formatAudio(ai.audio_seconds)} · Human ${formatAudio(human.audio_seconds)}`}
        />
      </dl>

      {data.sample_warning && (
        <p role="status" className="mt-4 flex items-start gap-2 rounded-lg bg-warning-soft px-3 py-2 text-warning">
          <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
          <span>
            <span className="font-medium">Small sample. </span>
            {data.sample_warning}
          </span>
        </p>
      )}
      {inProgress > 0 && (
        <p role="status" className="mt-3 flex items-center gap-2 text-muted-foreground">
          <Loader2 className="size-4 animate-spin motion-reduce:animate-none" aria-hidden />
          {inProgress} {inProgress === 1 ? 'call is' : 'calls are'} still being processed. Re-run the comparison
          when they finish.
        </p>
      )}
    </CompareSection>
  )
}

function Tile({ label, value, note }: { label: string; value: ReactNode; note?: string }) {
  return (
    <div className="rounded-lg border px-3 py-2.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="num mt-1 text-2xl font-semibold leading-tight">{value}</dd>
      {note && <dd className="num mt-0.5 text-xs text-muted-foreground">{note}</dd>}
    </div>
  )
}
