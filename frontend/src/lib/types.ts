// API response types — mirror backend/app/schemas.py. Keep the two in sync.

export type CheckState = 'ok' | 'warn' | 'fail'

export interface HealthCheck {
  name: string
  label: string
  state: CheckState
  detail: string
}

export interface HealthResponse {
  status: 'ok' | 'fail'
  version: string
  checks: HealthCheck[]
}

export interface StatsResponse {
  total_calls: number
  analysed_calls: number
  audio_seconds: number
  last_processed_at: string | null
}

export interface ProviderInfo {
  selected: string
  model: string
  key_present: boolean
}

export interface ScoreDimension {
  key: string
  label: string
  guide: string
}

export interface IntentRubric {
  buckets: Record<string, [number, number]>
  special: Record<string, string>
  signals: { positive: string[]; negative: string[] }
  objection_types: string[]
  ai_failure_patterns: string[]
}

export interface SettingsResponse {
  transcriber: ProviderInfo
  analyzer: ProviderInfo
  default_transcript_script: string
  concurrency: Record<string, number>
  limits: Record<string, number>
  mask_phones: boolean
  raw_audio_retention_days: number
  timezone: string
  passcode_enabled: boolean
  scorecard: { dimensions: ScoreDimension[]; quality_score: string }
  intent: IntentRubric
}

/** Standard error body from the API: {"error": {code, message, detail}} */
export interface ApiErrorBody {
  error: { code: string; message: string; detail: Record<string, unknown> }
}
