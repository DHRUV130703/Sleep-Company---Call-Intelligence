// "Action insights": what to do with this customer next.
//   1. What to pitch     — products from config/products.yaml that fit what the customer said (with their words)
//   2. What to do next?  — concrete steps, each with a "Say:" line and why it helps
//   3. Handle these concerns — objections and a better way to answer them
//   4. Questions still open — what the customer asked that wasn't answered

import { CircleCheck, Lightbulb, MessageCircleQuestion, ShieldAlert } from 'lucide-react'
import type { ReactNode } from 'react'
import { formatDay, humanize } from '@/lib/format'
import type { CallAnalysis } from '@/lib/types-calls'
import { EvidenceQuote } from './EvidenceQuote'

interface Props {
  analysis: CallAnalysis
  onSeek: (seconds: number) => void
}

export function ActionInsightsTab({ analysis, onSeek }: Props) {
  const pitches = analysis.pitch_opportunities
  const concerns = analysis.objections.filter((o) => o.better_response || !o.handled_well)
  return (
    <div className="space-y-6">
      <Section icon={<Lightbulb className="size-4 text-warning" />} title="What to pitch">
        {pitches === undefined ? (
          <p className="text-muted-foreground">
            This call was analysed before pitch suggestions existed. Click <span className="font-medium">Re-analyse</span>{' '}
            above to get them.
          </p>
        ) : pitches.length === 0 ? (
          <p className="text-muted-foreground">Nothing to pitch — the customer didn't show a buying need in this call.</p>
        ) : (
          <ul className="space-y-3">
            {pitches.map((p, i) => (
              <li key={i} className="rounded-lg border p-3">
                <div className="font-semibold">{p.product}</div>
                {p.fit_reason && (
                  <p className="mt-1">
                    <span className="text-muted-foreground">Why it fits: </span>
                    {p.fit_reason}
                  </p>
                )}
                <EvidenceQuote quote={p.evidence} t={p.t} verified={p.verified} onSeek={onSeek} className="mt-1.5" />
                {p.say && <SayLine text={p.say} />}
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section icon={<CircleCheck className="size-4 text-positive" />} title="What to do next?">
        {analysis.next_actions.length === 0 ? (
          <p className="text-muted-foreground">No follow-up needed.</p>
        ) : (
          <ol className="space-y-3">
            {analysis.next_actions.map((a, i) => (
              <li key={i} className="rounded-lg border p-3">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className="font-semibold">
                    {i + 1}. {a.title}
                  </span>
                  {a.due && <span className="num text-xs text-muted-foreground">Due {formatDay(a.due)}</span>}
                </div>
                {a.say && <SayLine text={a.say} />}
                {a.why && (
                  <p className="mt-2 flex gap-2 text-sm text-muted-foreground">
                    <CircleCheck className="mt-0.5 size-4 shrink-0 text-positive" aria-hidden />
                    {a.why}
                  </p>
                )}
              </li>
            ))}
          </ol>
        )}
      </Section>

      {concerns.length > 0 && (
        <Section icon={<ShieldAlert className="size-4 text-negative" />} title="Handle these concerns">
          <ul className="space-y-3">
            {concerns.map((o, i) => (
              <li key={i} className="rounded-lg border p-3">
                <div className="flex flex-wrap items-baseline gap-2">
                  <span className="font-semibold">{o.title || humanize(o.type)}</span>
                  <span className="rounded-full bg-surface-sunken px-2 py-0.5 text-xs text-muted-foreground">
                    {humanize(o.type)}
                  </span>
                </div>
                <EvidenceQuote quote={o.customer_quote} t={o.t} verified={o.verified} onSeek={onSeek} className="mt-1.5" />
                {o.better_response && (
                  <p className="mt-1.5">
                    <span className="text-muted-foreground">Better answer: </span>
                    {o.better_response}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {analysis.unanswered_questions.length > 0 && (
        <Section icon={<MessageCircleQuestion className="size-4 text-ai" />} title="Questions still open — answer these next time">
          <ul className="list-disc space-y-1 pl-5">
            {analysis.unanswered_questions.map((q, i) => (
              <li key={i}>{q}</li>
            ))}
          </ul>
        </Section>
      )}
    </div>
  )
}

function Section({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <section>
      <h3 className="mb-2 flex items-center gap-2 font-semibold">
        {icon}
        {title}
      </h3>
      {children}
    </section>
  )
}

function SayLine({ text }: { text: string }) {
  return (
    <p className="mt-2">
      👉 <span className="font-semibold">Say:</span> “{text}”
    </p>
  )
}
