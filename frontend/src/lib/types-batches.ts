// Shapes returned by backend/app/api/batches.py and uploads.py.

export interface BatchCounts {
  total: number
  ai: number
  human: number
  audio_seconds: number
  queued: number
  running: number
  done: number
  failed: number
  skipped: number
}

export interface BatchCall {
  id: number
  label: string
  agent_type: 'ai' | 'human'
  lead_id: number | null
  duration_s: number | null
  stage: string
  status: 'queued' | 'running' | 'done' | 'failed' | 'skipped'
  error_code: string | null
  error_message: string | null
  outcome: string | null
  quality_pct: number | null
  message?: string
}

export interface Batch {
  id: number
  name: string
  campaign: string
  source_type: string
  agent_type_mode: 'ai' | 'human' | 'column'
  status: 'processing' | 'done' | 'cancelled'
  created_at: string
  finished_at: string | null
  counts: BatchCounts
  eta_seconds: number | null
  skipped_inputs: { name: string; reason: string }[]
}

export interface BatchDetail extends Batch {
  calls: BatchCall[]
  last_event_id: number
}

export interface BatchEvent {
  event_id: number
  call_id: number
  stage: string
  status: BatchCall['status']
  message: string
  progress: number
}

export interface SheetPreview {
  sheet_id: string
  filename: string
  headers: string[]
  rows: Record<string, string>[]
  total_rows: number
  mapping: Record<string, string | null>
  fields: string[]
}

export interface SheetCheck {
  total_rows: number
  valid: number
  duplicates: number
  problems: { row: number; message: string }[]
  problem_count: number
  by_agent_type: { ai: number; human: number }
  leads: number
  stacked_phones: number
}

export type AgentMode = 'ai' | 'human' | 'column'

export interface BatchCreate {
  name: string
  campaign: string
  agent_type_mode: AgentMode
  transcript_script: 'roman' | 'devanagari' | 'english'
  files?: { upload_id: string; agent_type?: 'ai' | 'human' }[]
  sheet?: { sheet_id: string; mapping: Record<string, string | null> }
  links?: { url: string; label?: string; agent_type?: 'ai' | 'human' }[]
}
