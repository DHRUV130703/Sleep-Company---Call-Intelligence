import { Bot, Shuffle, UserRound } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { AgentMode } from '@/lib/types-batches'
import { cn } from '@/lib/utils'

export interface Options {
  mode: AgentMode
  name: string
  campaign: string
  script: 'roman' | 'devanagari' | 'english'
}

const MODES: { value: AgentMode; label: string; hint: string; icon: typeof Bot; tone: string }[] = [
  { value: 'ai', label: 'AI voice bot', hint: 'Every call is the bot', icon: Bot, tone: 'peer-checked:border-ai peer-checked:bg-ai-soft' },
  { value: 'human', label: 'Human agents', hint: 'Every call is a person', icon: UserRound, tone: 'peer-checked:border-human peer-checked:bg-human-soft' },
  { value: 'column', label: 'Both (mixed)', hint: 'Set per file, column or list', icon: Shuffle, tone: 'peer-checked:border-foreground peer-checked:bg-surface-sunken' },
]

export function BatchOptions({ value, onChange }: { value: Options; onChange: (v: Options) => void }) {
  const set = (patch: Partial<Options>) => onChange({ ...value, ...patch })
  return (
    <div className="space-y-5">
      <fieldset>
        <legend className="mb-2 text-sm font-medium">Who is on these calls?</legend>
        <div className="grid gap-2 sm:grid-cols-3">
          {MODES.map(({ value: v, label, hint, icon: Icon, tone }) => (
            <label key={v} className="relative cursor-pointer">
              <input
                type="radio"
                name="agent-mode"
                value={v}
                checked={value.mode === v}
                onChange={() => set({ mode: v })}
                className="peer sr-only"
              />
              <span
                className={cn(
                  'flex items-center gap-3 rounded-lg border bg-surface px-3 py-2.5 transition-colors',
                  'peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-ring',
                  tone,
                )}
              >
                <Icon className="size-5 shrink-0" aria-hidden />
                <span>
                  <span className="block font-medium">{label}</span>
                  <span className="block text-xs text-muted-foreground">{hint}</span>
                </span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="space-y-1.5 sm:col-span-1">
          <Label htmlFor="batch-name">Batch name</Label>
          <Input id="batch-name" placeholder="e.g. Week 40" value={value.name} onChange={(e) => set({ name: e.target.value })} />
        </div>
        <div className="space-y-1.5 sm:col-span-1">
          <Label htmlFor="campaign">Campaign / purpose (optional)</Label>
          <Input
            id="campaign"
            placeholder="Follow-up calls to mattress enquiries"
            value={value.campaign}
            onChange={(e) => set({ campaign: e.target.value })}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="script">Transcript script</Label>
          <select
            id="script"
            value={value.script}
            onChange={(e) => set({ script: e.target.value as Options['script'] })}
            className="h-9 w-full rounded-md border bg-surface px-3 text-sm"
          >
            <option value="roman">Hinglish (Roman letters)</option>
            <option value="devanagari">Hindi (Devanagari)</option>
            <option value="english">English (translated)</option>
          </select>
        </div>
      </div>
    </div>
  )
}
