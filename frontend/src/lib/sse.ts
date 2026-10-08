// Live batch progress over Server-Sent Events, with an automatic fallback to polling.

import { useEffect, useRef, useState } from 'react'
import type { BatchEvent } from '@/lib/types-batches'

/**
 * Calls `onEvent` for every progress event of a batch. Returns `live` = false when the stream
 * dropped, so the caller can poll instead (the browser also keeps retrying the stream).
 */
export function useBatchEvents(
  batchId: number,
  afterId: number | undefined,
  enabled: boolean,
  onEvent: (e: BatchEvent) => void,
  onFinished: () => void,
) {
  const [live, setLive] = useState(true)
  const handlers = useRef({ onEvent, onFinished })
  handlers.current = { onEvent, onFinished }

  useEffect(() => {
    if (!enabled || afterId === undefined || typeof EventSource === 'undefined') return
    const source = new EventSource(`/api/batches/${batchId}/events?after=${afterId}`)
    source.onopen = () => setLive(true)
    source.onmessage = (msg) => {
      try {
        handlers.current.onEvent(JSON.parse(msg.data) as BatchEvent)
      } catch {
        /* ignore malformed message */
      }
    }
    source.addEventListener('finished', () => {
      handlers.current.onFinished()
      source.close()
    })
    source.onerror = () => setLive(false)
    return () => source.close()
    // Re-open only when the batch changes — not on every new event id.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [batchId, enabled, afterId === undefined])

  return { live }
}
