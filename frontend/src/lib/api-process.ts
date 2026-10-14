// Processing driven by the open page (backend pipeline/tick.py). Used on Vercel, which has no worker.

import { request } from './api'

export interface TickResult {
  /** False where a background worker does the processing (local use): the page stops asking. */
  enabled: boolean
  /** The step that was just run, or null if nothing was due. */
  processed?: { call_id: number; stage: string } | null
  queued?: number
  running?: number
  /** Seconds until the next waiting step is due (e.g. checking back on a transcript). */
  next_in_s?: number | null
}

export const processApi = {
  tick: () => request<TickResult>('/process/tick', { method: 'POST' }),
}
