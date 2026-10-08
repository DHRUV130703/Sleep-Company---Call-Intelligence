// Call list + Call Detail response types — mirror backend/app/api/views.py (call_row, lead_row),
// backend/app/api/calls.py (call_detail) and the grounded analysis from backend/app/pipeline/analysis.py.

export type AgentType = 'ai' | 'human'
export type CallStatus = 'queued' | 'running' | 'done' | 'failed' | 'skipped'
export type Mood = 'positive' | 'neutral' | 'negative'

/** One row of GET /api/calls (also the top level of GET /api/calls/{id}). */
export interface CallRow {
  id: number
  batch_id: number
  label: string
  agent_type: AgentType
  agent_name: string
  campaign: string
  lead_id: number | null
  lead_name: string | null
  call_datetime: string | null
  duration_s: number | null
  stage: string
  status: CallStatus
  error_code: string | null
  error_message: string | null
  source_url: string | null
  outcome: string | null
  intent_score: number | null
  intent_bucket: string | null
  quality_pct: number | null
  language: string | null
  one_liner: string | null
}

export interface CallListResponse {
  items: CallRow[]
  total: number
  page: number
  page_size: number
}

export interface CallFilters {
  batch_id?: number
  lead_id?: number
  agent_type?: AgentType
  status?: CallStatus
  q?: string
  page?: number
  page_size?: number
}

export interface LeadSummary {
  id: number
  name: string
  has_name: boolean
  phone: string | null
  owner: string
  assignee: string
  status: string
  status_category: string
  intent_score: number | null
  intent_bucket: string | null
  last_call_at: string | null
}

export interface TranscriptSegment {
  i: number
  speaker: string
  role: 'agent' | 'customer'
  start: number
  end: number
  /** As spoken, in the original script (e.g. Hindi in Devanagari). */
  text: string
  /** The same words written in English letters — not a translation. */
  text_roman: string
}

export interface Transcript {
  provider: string
  model: string
  script: string
  segments: TranscriptSegment[]
  /** True when some lines are in a non-Latin script, so the "English letters" toggle is useful. */
  has_other_script: boolean
}

// ---- Analysis (contracts.CallAnalysis after grounding) ----

/** Every quote shown as evidence carries `verified` (passed grounding) and `t` (seconds, -1 = unknown). */
export interface ScoreItem {
  key: string
  score: number
  reason: string
  evidence: string
  t: number
  verified: boolean
}

export interface KeyMoment {
  t: number
  type: string
  label: string
  quote: string
  verified: boolean
}

export interface NextAction {
  title: string
  say: string
  why: string
  when: string
  due: string | null
}

export interface Objection {
  type: string
  title: string
  customer_quote: string
  t: number
  handling: string
  handled_well: boolean
  customer_satisfied: boolean
  better_response: string
  verified: boolean
}

export interface BantItem {
  status: 'known' | 'partial' | 'unknown'
  value: string
  evidence: string
  verified: boolean
}

export interface PitchOpportunity {
  product: string
  fit_reason: string
  evidence: string
  say: string
  t: number
  verified: boolean
}

export interface FailurePattern {
  pattern: string
  description: string
  quote: string
  t: number
  verified: boolean
}

export interface CallAnalysis {
  language: string
  summary: { one_liner: string; bullets: string[] }
  customer: {
    name: string
    city: string
    pincode: string
    products_discussed: string[]
    size: string
    budget: string
    pain_points: string[]
    competitors_mentioned: string[]
  }
  intent: { score: number; bucket: string; positive_factors: string[]; negative_factors: string[] }
  objections: Objection[]
  bant: Record<'budget' | 'authority' | 'need' | 'timeline', BantItem>
  outcome: {
    disposition: string
    next_step: string
    next_step_when: string
    next_step_due: string | null
    escalated: boolean
  }
  mood: { start: Mood; end: Mood; trajectory: 'improved' | 'same' | 'worsened' }
  scorecard: ScoreItem[]
  key_moments: KeyMoment[]
  friction_points: string[]
  unanswered_questions: string[]
  next_actions: NextAction[]
  /** Added in prompt v2 — older analyses don't have it until re-analysed. */
  pitch_opportunities?: PitchOpportunity[]
  ai_failure_patterns: FailurePattern[]
  quality_pct: number | null
  review_score: number | null
  prompt_version: string
  model: string
  created_at: string
}

/** Deterministic metrics computed in Python (PRD §7.2). */
export type CallMetrics = Record<string, number | boolean>

/** GET /api/calls/{id} */
export interface CallDetail extends CallRow {
  lead: LeadSummary | null
  has_audio: boolean
  transcript: Transcript | null
  analysis: CallAnalysis | null
  metrics: CallMetrics | null
  metric_labels: Record<string, string>
}
