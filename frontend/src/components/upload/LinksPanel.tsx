import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { parseLinks } from '@/lib/upload/helpers'
import { cn } from '@/lib/utils'

export interface LinksState {
  single: string
  ai: string
  human: string
}

export function LinksPanel({ value, mixed, onChange }: { value: LinksState; mixed: boolean; onChange: (v: LinksState) => void }) {
  if (!mixed) {
    return <LinkBox id="links" label="Recording links" value={value.single} onChange={(single) => onChange({ ...value, single })} />
  }
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <LinkBox id="links-ai" label="AI voice bot recordings" tone="ai" value={value.ai} onChange={(ai) => onChange({ ...value, ai })} />
      <LinkBox
        id="links-human"
        label="Human agent recordings"
        tone="human"
        value={value.human}
        onChange={(human) => onChange({ ...value, human })}
        hint="Use calls of the same kind (same campaign or purpose) so the comparison is fair."
      />
    </div>
  )
}

function LinkBox({ id, label, value, onChange, tone, hint }: {
  id: string
  label: string
  value: string
  onChange: (v: string) => void
  tone?: 'ai' | 'human'
  hint?: string
}) {
  const links = parseLinks(value)
  const bad = links.filter((l) => !l.valid).length
  return (
    <div className={cn('space-y-1.5 rounded-xl border bg-surface p-4',
      tone === 'ai' && 'border-l-4 border-l-ai', tone === 'human' && 'border-l-4 border-l-human')}>
      <Label htmlFor={id}>{label}</Label>
      <Textarea
        id={id}
        rows={7}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={'A1 | https://example.com/audio/A1.mp3\nhttps://example.com/audio/A2.mp3'}
        className="font-mono text-xs"
        spellCheck={false}
      />
      <p className="text-xs text-muted-foreground" aria-live="polite">
        One link per line. Add a label before a | if you want a name for the call.
        {links.length > 0 && (
          <span className={cn('num ml-1', bad ? 'text-negative' : 'text-positive')}>
            {links.length - bad} valid{bad > 0 && ` · ${bad} not a valid http(s) link`}
          </span>
        )}
      </p>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  )
}
