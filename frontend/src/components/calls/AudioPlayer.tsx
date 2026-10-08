// Waveform audio player for one call (PRD §6.4 Conversations tab).
// wavesurfer.js draws the waveform; key-moment markers are plain buttons positioned by percentage.

import { Pause, Play, RotateCcw, RotateCw, VolumeX } from 'lucide-react'
import { useEffect, useImperativeHandle, useRef, useState, type Ref } from 'react'
import WaveSurfer from 'wavesurfer.js'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { formatClock } from '@/lib/format'
import { cn } from '@/lib/utils'
import { TONE_BG, type MarkerTone } from './moments'

/** What the parent can do with the player (via `ref`). */
export interface AudioPlayerHandle {
  seek: (seconds: number) => void
}

export interface WaveMarker {
  t: number
  label: string
  tone: MarkerTone
}

interface Props {
  /** Audio URL, or null when the call has no audio. */
  src: string | null
  /** 'ai' or 'human' — colours the played part of the waveform. */
  accent: 'ai' | 'human'
  markers?: WaveMarker[]
  /** Used to place markers before the audio has loaded. */
  durationHint?: number | null
  onTimeUpdate?: (seconds: number) => void
  ref?: Ref<AudioPlayerHandle>
}

const SPEEDS = [1, 1.25, 1.5, 2]

/** Colours come from tokens.css, so the waveform follows light/dark mode. */
function waveColors(accent: 'ai' | 'human') {
  const css = getComputedStyle(document.documentElement)
  return {
    waveColor: css.getPropertyValue('--text-muted').trim() || 'gray',
    progressColor: css.getPropertyValue(`--${accent}`).trim() || 'blue',
    cursorColor: css.getPropertyValue('--text').trim() || 'black',
  }
}

export function AudioPlayer({ src, accent, markers = [], durationHint, onTimeUpdate, ref }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const wsRef = useRef<WaveSurfer | null>(null)
  const onTimeRef = useRef(onTimeUpdate)
  const [ready, setReady] = useState(false)
  const [failed, setFailed] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [current, setCurrent] = useState(0)
  const [duration, setDuration] = useState(0)
  const [speed, setSpeed] = useState(1)

  useEffect(() => {
    onTimeRef.current = onTimeUpdate
  }, [onTimeUpdate])

  useEffect(() => {
    if (!src || !containerRef.current) return
    const ws = WaveSurfer.create({
      container: containerRef.current,
      url: src,
      height: 64,
      barWidth: 2,
      barGap: 1,
      barRadius: 2,
      normalize: true,
      dragToSeek: true,
      ...waveColors(accent),
    })
    wsRef.current = ws

    // Only re-render ~10 times a second while playing, not on every animation frame.
    let lastTick = -1
    const report = (t: number) => {
      const tick = Math.floor(t * 10)
      if (tick === lastTick) return
      lastTick = tick
      setCurrent(t)
      onTimeRef.current?.(t)
    }

    const unsubs = [
      ws.on('ready', (d) => {
        setDuration(d)
        setReady(true)
      }),
      ws.on('timeupdate', report),
      ws.on('play', () => setPlaying(true)),
      ws.on('pause', () => setPlaying(false)),
      ws.on('finish', () => setPlaying(false)),
      ws.on('error', () => setFailed(true)),
    ]

    // Re-colour when the theme (.dark on <html>) changes.
    const observer = new MutationObserver(() => ws.setOptions(waveColors(accent)))
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })

    return () => {
      observer.disconnect()
      unsubs.forEach((off) => off())
      ws.destroy()
      wsRef.current = null
      setReady(false)
      setFailed(false)
      setPlaying(false)
      setCurrent(0)
      setSpeed(1)
    }
  }, [src, accent])

  /** Jump to a time and start playing from there. */
  function seek(seconds: number) {
    const ws = wsRef.current
    if (!ws) return
    ws.setTime(Math.max(0, seconds))
    void ws.play()
  }

  useImperativeHandle(ref, () => ({ seek }))

  function changeSpeed(rate: number) {
    setSpeed(rate)
    wsRef.current?.setPlaybackRate(rate)
  }

  if (!src || failed) {
    return (
      <div className="flex items-center gap-3 rounded-xl border bg-surface px-4 py-5 text-muted-foreground">
        <VolumeX className="size-5 shrink-0" aria-hidden />
        <span>
          {failed
            ? "The audio couldn't be loaded. The transcript and analysis below are still available."
            : 'No audio is stored for this call (it may have been removed by data retention).'}
        </span>
      </div>
    )
  }

  const total = duration || durationHint || 0
  const iconBtn = 'size-9'

  return (
    <div className="rounded-xl border bg-surface p-4">
      <div className="relative">
        <div ref={containerRef} className={cn(!ready && 'opacity-0')} aria-hidden />
        {!ready && <Skeleton className="absolute inset-0 h-16" />}
        {total > 0 &&
          markers
            .filter((m) => m.t >= 0 && m.t <= total)
            .map((m, i) => (
              <button
                key={`${m.t}-${i}`}
                type="button"
                title={`${formatClock(m.t)} · ${m.label}`}
                aria-label={`Jump to ${formatClock(m.t)}: ${m.label}`}
                onClick={() => seek(m.t)}
                className="group absolute -top-1.5 flex h-[calc(100%+0.75rem)] w-3 -translate-x-1/2 justify-center rounded-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                style={{ left: `${(m.t / total) * 100}%` }}
              >
                <span className={cn('h-full w-0.5 opacity-70 group-hover:opacity-100', TONE_BG[m.tone])} />
                <span className={cn('absolute top-0 size-2 rounded-full', TONE_BG[m.tone])} />
              </button>
            ))}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2">
        <Button variant="ghost" size="icon" className={iconBtn} aria-label="Back 10 seconds" onClick={() => wsRef.current?.skip(-10)} disabled={!ready}>
          <RotateCcw />
        </Button>
        <Button size="icon" className={iconBtn} aria-label={playing ? 'Pause' : 'Play'} onClick={() => void wsRef.current?.playPause()} disabled={!ready}>
          {playing ? <Pause /> : <Play />}
        </Button>
        <Button variant="ghost" size="icon" className={iconBtn} aria-label="Forward 10 seconds" onClick={() => wsRef.current?.skip(10)} disabled={!ready}>
          <RotateCw />
        </Button>
        <span className="num font-mono text-xs text-muted-foreground">
          {formatClock(current)} / {formatClock(total)}
        </span>
        <div className="ml-auto flex gap-1" role="group" aria-label="Playback speed">
          {SPEEDS.map((rate) => (
            <Button
              key={rate}
              variant={speed === rate ? 'secondary' : 'ghost'}
              size="sm"
              aria-pressed={speed === rate}
              onClick={() => changeSpeed(rate)}
              disabled={!ready}
            >
              <span className="num">{rate}×</span>
            </Button>
          ))}
        </div>
      </div>
    </div>
  )
}
