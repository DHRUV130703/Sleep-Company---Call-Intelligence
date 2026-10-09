// API calls and URL helpers for the AI vs Human report. Uses the shared `request` from api.ts.

import { request } from './api'
import type { CompareOptions, CompareResult, CompareScope, ReportFormat, SavedReport } from './types-compare'

// ---------------------------------------------------------------------------
// Scope <-> page URL (?batches=1,2&campaign=…&from=…&to=…&comparable=1)
// ---------------------------------------------------------------------------

export function scopeFromParams(params: URLSearchParams): CompareScope {
  const batchIds = (params.get('batches') ?? '')
    .split(',')
    .map((x) => Number(x))
    .filter((n) => Number.isInteger(n) && n > 0)
  return {
    batchIds,
    campaign: params.get('campaign') ?? '',
    dateFrom: params.get('from') ?? '',
    dateTo: params.get('to') ?? '',
    comparableOnly: params.get('comparable') === '1',
  }
}

export function scopeToParams(scope: CompareScope): URLSearchParams {
  const p = new URLSearchParams()
  if (scope.batchIds.length) p.set('batches', scope.batchIds.join(','))
  if (scope.campaign) p.set('campaign', scope.campaign)
  if (scope.dateFrom) p.set('from', scope.dateFrom)
  if (scope.dateTo) p.set('to', scope.dateTo)
  if (scope.comparableOnly) p.set('comparable', '1')
  return p
}

// ---------------------------------------------------------------------------
// Scope -> backend query string (?batch_ids=1,2&campaign=…&date_from=…&date_to=…&comparable_only=true)
// ---------------------------------------------------------------------------

function scopeQuery(scope: CompareScope, force = false): string {
  const p = new URLSearchParams()
  if (scope.batchIds.length) p.set('batch_ids', scope.batchIds.join(','))
  if (scope.campaign) p.set('campaign', scope.campaign)
  if (scope.dateFrom) p.set('date_from', scope.dateFrom)
  // Include the whole "to" day.
  if (scope.dateTo) p.set('date_to', `${scope.dateTo}T23:59:59`)
  if (scope.comparableOnly) p.set('comparable_only', 'true')
  if (force) p.set('force', 'true')
  const qs = p.toString()
  return qs ? `?${qs}` : ''
}

export const compareApi = {
  /** The full report. `force` rebuilds it even if a cached result exists. */
  result: (scope: CompareScope, force = false) => request<CompareResult>(`/compare${scopeQuery(scope, force)}`),
  options: () => request<CompareOptions>('/compare/options'),
  /** Re-analyse bot calls reviewed with an older prompt (they lack "better" lines). */
  updateBotReviews: (scope: CompareScope) =>
    request<{ queued: number }>(`/compare/update-bot-reviews${scopeQuery(scope)}`, { method: 'POST' }),
  /** Plain download links (used in <a href download>). Each download is also saved with a public link. */
  exportUrl: (scope: CompareScope, kind: ReportFormat) => `/api/compare/export.${kind}${scopeQuery(scope)}`,
  /** Save the report in every format; returns their public links. */
  saveAll: (scope: CompareScope) =>
    request<{ reports: SavedReport[] }>(`/compare/reports${scopeQuery(scope)}`, { method: 'POST' }),
  /** Print-ready report page; opens the browser's "Save as PDF" dialog. */
  reportUrl: (scope: CompareScope) => {
    const qs = scopeQuery(scope)
    return `/api/compare/report.html${qs ? `${qs}&` : '?'}print=1`
  },
}
