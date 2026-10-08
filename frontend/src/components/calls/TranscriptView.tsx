// Chat-style transcript: Agent on the left, Customer on the right (PRD §6.4).
// The line being played is highlighted and kept in view; click a line to jump there; search filters lines.
// "Original" shows each line as spoken (e.g. Hindi in Devanagari); "English letters" shows the same words
// written in Roman script — same language, not a translation.

import { LocateFixed, Search } from 'lucide-react'
import { memo, useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { formatClock } from '@/lib/format'
import { readPref, writePref } from '@/lib/storage'
import type { TranscriptSegment } from '@/lib/types-calls'
import { cn } from '@/lib/utils'

type Script = 'original' | 'roman'

interface Props {
  segments: TranscriptSegment[]
  hasOtherScript: boolean
  currentTime: number
  accent: 'ai' | 'human'
  onSeek: (seconds: number) => void
}

const SCROLL_KEYS = new Set(['ArrowUp', 'ArrowDown', 'PageUp', 'PageDown', 'Home', 'End'])

/** Index of the last segment that has started by `t`, or -1 before the first one. */
function activeIndex(segments: TranscriptSegment[], t: number): number {
  let found = -1
  for (let i = 0; i < segments.length; i++) {
    if (segments[i].start <= t) found = i
    else break
  }
  return found
}

export function TranscriptView({ segments, hasOtherScript, currentTime, accent, onSeek }: Props) {
  const [script, setScriptState] = useState<Script>(() => readPref<Script>('transcriptScript', 'original'))
  const setScript = (s: Script) => {
    setScriptState(s)
    writePref('transcriptScript', s)
  }
  const showRoman = hasOtherScript && script === 'roman'
  const textOf = useCallback((s: TranscriptSegment) => (showRoman ? s.text_roman || s.text : s.text), [showRoman])
  const [query, setQuery] = useState('')
  const [follow, setFollow] = useState(true)
  const scrollRef = useRef<HTMLDivElement>(null)

  const q = query.trim().toLowerCase()
  const visible = useMemo(
    () => (q ? segments.filter((s) => textOf(s).toLowerCase().includes(q)) : segments),
    [segments, q, textOf],
  )
  const active = activeIndex(segments, currentTime)
  const activeSegment = active >= 0 ? segments[active] : null

  // Keep the playing line in view — but only while the user hasn't scrolled away themselves.
  useEffect(() => {
    if (!follow || !activeSegment || !scrollRef.current) return
    const box = scrollRef.current
    const el = box.querySelector<HTMLElement>(`[data-seg="${activeSegment.i}"]`)
    if (!el) return
    const top = el.offsetTop // the scroll box is `relative`, so this is relative to it
    const outOfView = top < box.scrollTop || top + el.offsetHeight > box.scrollTop + box.clientHeight
    if (outOfView) box.scrollTo({ top: Math.max(0, top - box.clientHeight / 3), behavior: 'smooth' })
  }, [activeSegment, follow])

  // Wheel / touch / keyboard scrolling means "I'm reading elsewhere": stop following.
  const stopFollowing = () => setFollow(false)
  const onScrollKey = (e: KeyboardEvent) => {
    if (SCROLL_KEYS.has(e.key)) setFollow(false)
  }

  const seek = useCallback(
    (t: number) => {
      setFollow(true)
      onSeek(t)
    },
    [onSeek],
  )

  if (segments.length === 0) {
    return <p className="rounded-xl border bg-surface p-6 text-muted-foreground">No transcript yet.</p>
  }

  return (
    <div className="flex flex-col rounded-xl border bg-surface">
      <div className="flex flex-wrap items-center gap-2 border-b p-3">
        <div className="relative min-w-0 flex-1">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search transcript"
            aria-label="Search transcript"
            className="pl-8"
          />
        </div>
        {hasOtherScript && <ScriptToggle value={script} onChange={setScript} />}
        {q && (
          <span className="num text-xs text-muted-foreground" aria-live="polite">
            {visible.length} {visible.length === 1 ? 'match' : 'matches'}
          </span>
        )}
        {!follow && (
          <Button variant="outline" size="sm" onClick={() => setFollow(true)}>
            <LocateFixed />
            Follow playback
          </Button>
        )}
      </div>

      <div
        ref={scrollRef}
        onWheel={stopFollowing}
        onTouchMove={stopFollowing}
        onKeyDown={onScrollKey}
        className="relative max-h-[60vh] space-y-3 overflow-y-auto p-3 lg:max-h-[640px]"
      >
        {visible.length === 0 && <p className="py-6 text-center text-muted-foreground">No lines match “{query}”.</p>}
        {visible.map((s) => (
          <Line
            key={s.i}
            seg={s}
            text={textOf(s)}
            active={s.i === activeSegment?.i}
            query={q}
            accent={accent}
            onSeek={seek}
          />
        ))}
      </div>
    </div>
  )
}

/** Original script ⇄ English letters (same words, not translated). */
function ScriptToggle({ value, onChange }: { value: Script; onChange: (s: Script) => void }) {
  const options: { value: Script; label: string }[] = [
    { value: 'original', label: 'Original' },
    { value: 'roman', label: 'English letters' },
  ]
  return (
    <div role="radiogroup" aria-label="Transcript script" className="inline-flex rounded-lg border bg-surface-sunken p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          onClick={() => onChange(o.value)}
          title={o.value === 'roman' ? 'Same words written in English letters — not a translation' : 'As spoken'}
          className={cn(
            'rounded-md px-2.5 py-1 text-xs font-medium outline-none focus-visible:ring-3 focus-visible:ring-ring/50',
            value === o.value ? 'bg-surface text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground',
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

interface LineProps {
  seg: TranscriptSegment
  text: string
  active: boolean
  query: string
  accent: 'ai' | 'human'
  onSeek: (t: number) => void
}

const Line = memo(function Line({ seg, text, active, query, accent, onSeek }: LineProps) {
  const isAgent = seg.role === 'agent'
  return (
    <div data-seg={seg.i} className={cn('flex', isAgent ? 'justify-start' : 'justify-end')}>
      <button
        type="button"
        onClick={() => onSeek(seg.start)}
        aria-current={active ? 'true' : undefined}
        aria-label={`${isAgent ? 'Agent' : 'Customer'} at ${formatClock(seg.start)}. Play from here.`}
        className={cn(
          'max-w-[85%] rounded-xl px-3 py-2 text-left transition-shadow outline-none focus-visible:ring-3 focus-visible:ring-ring/50',
          isAgent ? (accent === 'ai' ? 'bg-ai-soft' : 'bg-human-soft') : 'bg-surface-sunken',
          active && (accent === 'ai' ? 'ring-2 ring-ai' : 'ring-2 ring-human'),
        )}
      >
        <span className="mb-0.5 flex items-center gap-2 text-xs text-muted-foreground">
          <span className={cn('font-medium', isAgent && (accent === 'ai' ? 'text-ai' : 'text-human'))}>
            {isAgent ? 'Agent' : 'Customer'}
          </span>
          <span className="num font-mono">{formatClock(seg.start)}</span>
        </span>
        <span className="block">
          <Highlighted text={text} query={query} />
        </span>
      </button>
    </div>
  )
})

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/** Wraps every match of `query` in <mark>. */
function Highlighted({ text, query }: { text: string; query: string }) {
  if (!query) return <>{text}</>
  const parts = text.split(new RegExp(`(${escapeRegExp(query)})`, 'gi'))
  return (
    <>
      {parts.map((part, i) =>
        part.toLowerCase() === query ? (
          <mark key={i} className="rounded-sm bg-warning-soft px-0.5 text-foreground">
            {part}
          </mark>
        ) : (
          part
        ),
      )}
    </>
  )
}
