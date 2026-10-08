// Typed calls endpoints (PRD §8.5). Everything goes through `request` in api.ts.

import { request } from './api'
import type { CallDetail, CallFilters, CallListResponse } from './types-calls'

type Ok = { ok: boolean }

function toQuery(filters: CallFilters): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== '' && value !== null) params.set(key, String(value))
  }
  const qs = params.toString()
  return qs ? `?${qs}` : ''
}

export const callsApi = {
  list: (filters: CallFilters = {}) => request<CallListResponse>(`/calls${toQuery(filters)}`),
  get: (id: number) => request<CallDetail>(`/calls/${id}`),
  retry: (id: number) => request<Ok>(`/calls/${id}/retry`, { method: 'POST' }),
  reanalyze: (id: number) => request<Ok>(`/calls/${id}/reanalyze`, { method: 'POST' }),
  swapSpeakers: (id: number) => request<Ok>(`/calls/${id}/swap-speakers`, { method: 'POST' }),
}

/** URL for the <audio>/wavesurfer element. Supports HTTP Range, so seeking works. */
export function callAudioUrl(id: number): string {
  return `/api/calls/${id}/audio`
}
