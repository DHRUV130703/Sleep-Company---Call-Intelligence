import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CircleCheck, CircleX, RefreshCw, TriangleAlert } from 'lucide-react'
import type { ReactNode } from 'react'
import { PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { api, ApiError } from '@/lib/api'
import { humanize } from '@/lib/format'
import type { CheckState, HealthCheck, SettingsResponse } from '@/lib/types'
import { cn } from '@/lib/utils'

export default function SettingsPage() {
  return (
    <>
      <PageHeader
        title="Settings"
        description={
          <>
            Secrets and machine settings live in <Code>.env</Code>. Business rules live in{' '}
            <Code>config/scorecard.yaml</Code> and <Code>config/intent_rubric.yaml</Code>.
          </>
        }
      />
      <div className="grid gap-6 xl:grid-cols-2">
        <HealthCard />
        <SettingsCards />
      </div>
    </>
  )
}

// ---------------------------------------------------------------------------
// System health
// ---------------------------------------------------------------------------

const STATE_ICON: Record<CheckState, { icon: typeof CircleCheck; className: string; label: string }> = {
  ok: { icon: CircleCheck, className: 'text-positive', label: 'OK' },
  warn: { icon: TriangleAlert, className: 'text-warning', label: 'Warning' },
  fail: { icon: CircleX, className: 'text-negative', label: 'Problem' },
}

function HealthCard() {
  const health = useQuery({ queryKey: ['health'], queryFn: api.health, refetchInterval: 15_000 })

  return (
    <Card className="xl:row-span-2">
      <CardHeader>
        <CardTitle>System health</CardTitle>
        <CardDescription>
          {health.data
            ? health.data.status === 'ok'
              ? 'Everything needed to run is in place.'
              : 'Something needs attention before calls can be processed.'
            : 'Checking…'}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {health.isPending && <RowsSkeleton rows={8} />}
        {health.isError && <ErrorLine error={health.error} />}
        {health.data && (
          <ul className="divide-y" aria-live="polite">
            {health.data.checks.map((c) => (
              <HealthRow key={c.name} check={c} />
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

function HealthRow({ check }: { check: HealthCheck }) {
  const { icon: Icon, className, label } = STATE_ICON[check.state]
  return (
    <li className="flex items-start gap-3 py-3">
      <Icon className={cn('mt-0.5 size-[18px] shrink-0', className)} aria-label={label} />
      <div className="min-w-0">
        <div className="font-medium">{check.label}</div>
        <div className="break-words text-muted-foreground">{check.detail}</div>
      </div>
    </li>
  )
}

// ---------------------------------------------------------------------------
// Providers, processing, privacy, business rules
// ---------------------------------------------------------------------------

function SettingsCards() {
  const qc = useQueryClient()
  const settings = useQuery({ queryKey: ['settings'], queryFn: api.settings })
  const reload = useMutation({
    mutationFn: api.reloadConfig,
    onSuccess: (data) => {
      qc.setQueryData(['settings'], data)
      qc.invalidateQueries({ queryKey: ['health'] })
    },
  })

  if (settings.isPending) {
    return (
      <Card>
        <CardContent>
          <RowsSkeleton rows={6} />
        </CardContent>
      </Card>
    )
  }
  if (settings.isError) {
    return (
      <Card>
        <CardContent>
          <ErrorLine error={settings.error} />
        </CardContent>
      </Card>
    )
  }
  const s = settings.data

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>Providers & processing</CardTitle>
          <CardDescription>
            Change these in <Code>.env</Code>, then restart <Code>make dev</Code>.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-[minmax(0,10rem)_1fr] gap-x-4 gap-y-2.5">
            <Item label="Transcription">
              <ProviderValue name={s.transcriber.selected} model={s.transcriber.model} ok={s.transcriber.key_present} />
            </Item>
            <Item label="Analysis">
              <ProviderValue name={s.analyzer.selected} model={s.analyzer.model} ok={s.analyzer.key_present} />
            </Item>
            <Item label="Transcript script">{humanize(s.default_transcript_script)}</Item>
            <Item label="Concurrency">
              <span className="num">
                download {s.concurrency.download} · transcribe {s.concurrency.transcribe} · analyse{' '}
                {s.concurrency.analyze}
              </span>
            </Item>
            <Item label="Limits">
              <span className="num">
                {s.limits.max_file_gb} GB per file · {s.limits.max_zip_gb} GB per ZIP ·{' '}
                {s.limits.max_calls_per_batch} calls per batch
              </span>
            </Item>
            <Item label="Privacy">
              Phones {s.mask_phones ? 'masked' : 'visible'} · raw audio kept {s.raw_audio_retention_days} days
            </Item>
            <Item label="Timezone">{s.timezone}</Item>
          </dl>
        </CardContent>
      </Card>

      <Card className="xl:col-span-2">
        <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle>Scoring rules</CardTitle>
            <CardDescription>
              Read from <Code>config/*.yaml</Code>. Edit the files, then reload.
            </CardDescription>
          </div>
          <Button variant="outline" onClick={() => reload.mutate()} disabled={reload.isPending}>
            <RefreshCw className={cn('size-4', reload.isPending && 'animate-spin')} />
            Reload config
          </Button>
        </CardHeader>
        <CardContent className="space-y-6">
          {reload.isError && <ErrorLine error={reload.error} />}
          {reload.isSuccess && <p className="text-positive">Config reloaded.</p>}
          <RulesPreview s={s} />
        </CardContent>
      </Card>
    </>
  )
}

function RulesPreview({ s }: { s: SettingsResponse }) {
  const buckets = Object.entries(s.intent.buckets).sort((a, b) => b[1][0] - a[1][0])
  return (
    <div className="grid gap-8 lg:grid-cols-2">
      <section>
        <h3 className="mb-2 font-medium">Scorecard — 1 (poor) to 5 (excellent)</h3>
        <ol className="divide-y rounded-lg border">
          {s.scorecard.dimensions.map((d, i) => (
            <li key={d.key} className="flex gap-3 px-3 py-2.5">
              <span className="num w-5 shrink-0 text-muted-foreground">{i + 1}</span>
              <div>
                <div className="font-medium">{d.label}</div>
                {d.guide && <div className="text-muted-foreground">{d.guide}</div>}
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section className="space-y-6">
        <div>
          <h3 className="mb-2 font-medium">Intent buckets</h3>
          <ul className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {buckets.map(([name, [lo, hi]]) => (
              <li key={name} className="rounded-lg border px-3 py-2">
                <div className="font-medium">{humanize(name)}</div>
                <div className="num text-muted-foreground">
                  {lo}–{hi}
                </div>
              </li>
            ))}
          </ul>
        </div>
        <TagList title="Objection types" items={s.intent.objection_types} />
        <TagList title="AI failure patterns" items={s.intent.ai_failure_patterns} />
      </section>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Small pieces
// ---------------------------------------------------------------------------

function Item({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-words">{children}</dd>
    </>
  )
}

function ProviderValue({ name, model, ok }: { name: string; model: string; ok: boolean }) {
  return (
    <span className="inline-flex flex-wrap items-center gap-x-2">
      <span className="font-medium">{name}</span>
      <span className="font-mono text-xs text-muted-foreground">{model}</span>
      {ok ? (
        <span className="text-xs text-positive">✓ key set</span>
      ) : (
        <span className="text-xs text-warning">⚠ API key missing</span>
      )}
    </span>
  )
}

function TagList({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <h3 className="mb-2 font-medium">{title}</h3>
      <ul className="flex flex-wrap gap-1.5">
        {items.map((t) => (
          <li key={t} className="rounded-full bg-surface-sunken px-2.5 py-0.5 text-xs">
            {humanize(t)}
          </li>
        ))}
      </ul>
    </div>
  )
}

function Code({ children }: { children: ReactNode }) {
  return <code className="rounded bg-surface-sunken px-1 py-0.5 font-mono text-[0.85em]">{children}</code>
}

function RowsSkeleton({ rows }: { rows: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  )
}

function ErrorLine({ error }: { error: Error }) {
  const detail = error instanceof ApiError ? (error.detail.reason as string | undefined) : undefined
  return (
    <div role="alert" className="rounded-lg bg-negative-soft px-3 py-2 text-negative">
      <div className="font-medium">{error.message}</div>
      {detail && <pre className="mt-1 whitespace-pre-wrap font-mono text-xs">{detail}</pre>}
    </div>
  )
}
