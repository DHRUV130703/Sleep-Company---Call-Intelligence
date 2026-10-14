import { Loader2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { WORK_ADDED_EVENT } from '@/lib/api'
import { processApi, type TickResult } from '@/lib/api-process'

const PARALLEL = 2 // steps run at the same time from this tab (the server also enforces per-stage limits)
const IDLE_MS = 30_000 // with nothing to do, look for new work every 30 s (new uploads wake it at once)
const RETRY_MS = 15_000

/**
 * Keeps uploads moving while this tab is open: asks the server to run the next processing step,
 * over and over (see backend pipeline/tick.py). Shows how many calls are in progress.
 * Renders nothing, and stops asking, where a background worker does the processing instead.
 */
export function ProcessingDriver() {
  const [inProgress, setInProgress] = useState(0)

  useEffect(() => {
    let stopped = false
    const sleepers = new Set<() => void>()
    const sleep = (ms: number) =>
      new Promise<void>((resolve) => {
        const done = () => {
          clearTimeout(timer)
          sleepers.delete(done)
          resolve()
        }
        const timer = setTimeout(done, ms)
        sleepers.add(done)
      })
    const wakeAll = () => [...sleepers].forEach((wake) => wake())

    const loop = async (n: number) => {
      while (!stopped) {
        let r: TickResult
        try {
          r = await processApi.tick()
        } catch {
          await sleep(RETRY_MS) // offline, signed out, or a server error: try again later
          continue
        }
        if (!r.enabled) {
          stopped = true
          return
        }
        const left = (r.queued ?? 0) + (r.running ?? 0)
        setInProgress(left)
        if (r.processed) continue // more may be due right away
        if (left === 0) await sleep(IDLE_MS * (n + 1))
        else await sleep(Math.min(15_000, Math.max(1_000, (r.next_in_s ?? 2) * 1_000)))
      }
    }

    window.addEventListener(WORK_ADDED_EVENT, wakeAll)
    for (let n = 0; n < PARALLEL; n++) void loop(n)
    return () => {
      stopped = true
      wakeAll()
      window.removeEventListener(WORK_ADDED_EVENT, wakeAll)
    }
  }, [])

  if (inProgress === 0) return null
  return (
    <span
      role="status"
      title="Calls are processed while this app is open in a browser. Keep a tab open until they finish."
      className="hidden items-center gap-1.5 rounded-full bg-ai-soft px-2.5 py-1 text-[13px] text-ai sm:inline-flex"
    >
      <Loader2 className="size-3.5 animate-spin motion-reduce:animate-none" aria-hidden />
      Processing {inProgress} {inProgress === 1 ? 'call' : 'calls'} · keep this tab open
    </span>
  )
}
