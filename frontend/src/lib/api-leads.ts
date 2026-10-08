// Typed calls for All Conversations and Lead Details. Pages use these via TanStack Query.

import { request } from './api'
import type {
  FilterOptions,
  LeadAction,
  LeadBase,
  LeadDetail,
  LeadKpis,
  LeadListResponse,
  LeadNote,
} from './types-leads'

/** URL search-param names the leads filters use. The same names are sent to the API. */
export const LEAD_FILTER_KEYS = [
  'date_from',
  'date_to',
  'q',
  'batch_id',
  'campaign',
  'owner',
  'agent_type',
  'status',
  'status_category',
  'intent_bucket',
] as const

export type LeadFilterKey = (typeof LEAD_FILTER_KEYS)[number]
export type LeadFilters = Partial<Record<LeadFilterKey, string>>

/** Read the active filters out of the page URL (empty values are dropped). */
export function filtersFromParams(params: URLSearchParams): LeadFilters {
  const out: LeadFilters = {}
  for (const key of LEAD_FILTER_KEYS) {
    const value = params.get(key)
    if (value) out[key] = value
  }
  return out
}

/** Build "?a=1&b=2" for the API. `date_to` is a day, so we include the whole day. */
function toQuery(params: Record<string, string | number | undefined>): string {
  const qs = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === '') continue
    qs.set(key, key === 'date_to' ? `${value}T23:59:59` : String(value))
  }
  const s = qs.toString()
  return s ? `?${s}` : ''
}

export interface LeadListParams extends LeadFilters {
  sort?: string
  page?: number
  page_size?: number
}

const json = (body: unknown) => JSON.stringify(body)

export const leadsApi = {
  list: (params: LeadListParams) => request<LeadListResponse>(`/leads${toQuery({ ...params })}`),
  kpis: (filters: LeadFilters) => request<LeadKpis>(`/leads/kpis${toQuery({ ...filters })}`),
  filterOptions: () => request<FilterOptions>('/leads/filters'),
  detail: (id: number) => request<LeadDetail>(`/leads/${id}`),

  update: (id: number, body: { status?: string; assignee?: string }) =>
    request<LeadBase>(`/leads/${id}`, { method: 'PATCH', body: json(body) }),

  addAction: (leadId: number, body: { title: string; due_date?: string | null }) =>
    request<LeadAction>(`/leads/${leadId}/actions`, { method: 'POST', body: json(body) }),
  updateAction: (id: number, body: { done?: boolean; due_date?: string | null; title?: string }) =>
    request<LeadAction>(`/actions/${id}`, { method: 'PATCH', body: json(body) }),
  deleteAction: (id: number) => request<{ ok: boolean }>(`/actions/${id}`, { method: 'DELETE' }),

  addNote: (leadId: number, body: string) =>
    request<LeadNote>(`/leads/${leadId}/notes`, { method: 'POST', body: json({ body }) }),
  deleteNote: (id: number) => request<{ ok: boolean }>(`/notes/${id}`, { method: 'DELETE' }),
}
