// The only place the frontend talks to the backend. Pages call these functions via TanStack Query.

import type { ApiErrorBody, HealthResponse, SettingsResponse, StatsResponse } from './types'

/** Error thrown for any non-2xx response. `message` is safe to show to users. */
export class ApiError extends Error {
  readonly code: string
  readonly status: number
  readonly detail: Record<string, unknown>

  constructor(status: number, code: string, message: string, detail: Record<string, unknown> = {}) {
    super(message)
    this.status = status
    this.code = code
    this.detail = detail
  }
}

/** Call the backend. Throws ApiError with a user-friendly message on failure. */
export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`/api${path}`, {
      ...init,
      headers: init?.body instanceof FormData || init?.body instanceof Blob || init?.body instanceof ArrayBuffer
        ? init?.headers
        : { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch {
    throw new ApiError(0, 'NETWORK_ERROR', "Can't reach the LimeZip server. Is `make dev` running?")
  }

  if (!res.ok) {
    let body: Partial<ApiErrorBody> = {}
    try {
      body = await res.json()
    } catch {
      /* non-JSON error (e.g. proxy error page) */
    }
    const err = body.error
    throw new ApiError(
      res.status,
      err?.code ?? 'HTTP_ERROR',
      err?.message ?? `Request failed (HTTP ${res.status}).`,
      err?.detail ?? {},
    )
  }
  return (await res.json()) as T
}

export const api = {
  health: () => request<HealthResponse>('/health'),
  stats: () => request<StatsResponse>('/stats'),
  settings: () => request<SettingsResponse>('/settings'),
  reloadConfig: () => request<SettingsResponse>('/settings/reload-config', { method: 'POST' }),
}
