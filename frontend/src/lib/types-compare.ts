// Types for the AI voice bot vs human agents report (PRD §6.6).
// Mirror backend/app/pipeline/compare.py (build_comparison) and app/api/compare.py. Keep them in sync.

export type Side = 'ai' | 'human'

/** Every per-side value comes as a pair: AI first, Human second. */
export type PerSide<T> = Record<Side, T>

export interface RecordCounts {
  uploaded: number
  analysed: number
  failed: number
  not_connected: number
  in_progress: number
  audio_seconds: number
}

export interface SideScore {
  /** Average review score, 1–5. Null when no call on that side was reviewed. */
  avg_review: number | null
  /** Calls reviewed. */
  n: number
  /** Calls in scope. */
  of: number
}

export interface DimensionRow {
  key: string
  label: string
  ai: number | null
  human: number | null
  ai_n: number
  human_n: number
}

export interface PairRow {
  key: string
  label: string
  ai: number | null
  human: number | null
}

export interface SideSignals {
  mood_end: Partial<Record<'positive' | 'neutral' | 'negative', number>>
  mood_improved: number
  mood_worsened: number
  objections_total: number
  objections_handled_well: number
  friction_per_call: number
  unanswered_per_call: number
  escalated_pct: number
  avg_intent: number | null
}

export interface PatternEvidence {
  call_id: number
  label: string
  quote: string
  t: number
}

export interface FailurePattern {
  pattern: string
  count: number
  of: number
  evidence: PatternEvidence[]
}

export interface CompareCall {
  id: number
  label: string
  duration_s: number | null
  status: string
  error_code: string | null
  language: string | null
  outcome: string | null
  quality_pct: number | null
  review_score: number | null
  one_liner: string | null
}

export interface DifferenceEvidence {
  call_id: number
  quote: string
  t: number
  label: string
  agent_type: Side
}

export interface Difference {
  theme: string
  ai: string
  human: string
  why: string
  evidence: DifferenceEvidence[]
}

export type Priority = 'high' | 'medium' | 'low'

export interface RecommendedChange {
  priority: Priority
  change: string
  rationale: string
}

export interface Synthesis {
  verdict_headline: string
  differences: Difference[]
  ai_better: string[]
  human_better: string[]
  outcomes_paragraph: string
  recommended_changes: RecommendedChange[]
}

export interface CompareResult {
  scope: {
    batch_ids: number[]
    campaign: string
    date_from: string | null
    date_to: string | null
    comparable_only: boolean
  }
  generated_at: string
  records: PerSide<RecordCounts>
  sample_warning: string | null
  scores: PerSide<SideScore>
  dimensions: DimensionRow[]
  metrics: PairRow[]
  outcomes: PairRow[]
  signals: PerSide<SideSignals>
  failure_patterns: FailurePattern[]
  calls: PerSide<CompareCall[]>
  /** The written part. Null when the AI couldn't write it (see synthesis_error). */
  synthesis: Synthesis | null
  synthesis_error: string | null
}

export interface BatchOption {
  id: number
  name: string
  created_at: string
  ai: number
  human: number
}

export interface CompareOptions {
  batches: BatchOption[]
  campaigns: string[]
}

/** What the user picked in the scope picker. Lives in the URL search params. */
export interface CompareScope {
  batchIds: number[]
  campaign: string
  /** "YYYY-MM-DD" or "" */
  dateFrom: string
  /** "YYYY-MM-DD" or "" */
  dateTo: string
  comparableOnly: boolean
}
