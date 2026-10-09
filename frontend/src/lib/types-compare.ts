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

// ---------------------------------------------------------------------------
// Bot improvement plan (backend/app/pipeline/bot_improvement.py + bot_rca.py)
// ---------------------------------------------------------------------------

/** Points every example back to its call (and the moment in it) and its lead. */
export interface CallRef {
  call_id: number
  label: string
  lead_id: number | null
}

export type ImprovementPriority = 'high' | 'medium' | 'low' | 'none'
export type GapStatus = 'behind' | 'on_par' | 'ahead' | 'no_data'

export interface Verdict {
  status: 'behind' | 'on_par' | 'ahead' | 'no_benchmark' | 'no_data'
  label: string
  /** Human average minus bot average (1–5 scale). Positive = bot behind. */
  gap: number | null
  /** Bot average as % of the human average. */
  readiness_pct: number | null
  dimensions_behind: number
  dimensions_on_par: number
  dimensions_ahead: number
  /** % of calls ending with a sale, store visit, callback or other agreed step. */
  positive_outcome_pct: PerSide<number | null>
  top_levers: string[]
  points: string[]
}

export interface BotMoment extends CallRef {
  score: number
  reason: string
  /** Verified quote, or "" when the quote couldn't be verified. */
  quote: string
  t: number
  better: string
}

export interface HumanMoment extends CallRef {
  score: number
  reason: string
  quote: string
  t: number
}

export interface ImprovementParameter {
  key: string
  label: string
  area: string
  fix: string
  ai: number | null
  human: number | null
  target: number
  gap: number | null
  weak_calls: number
  of: number
  weak_share: number
  priority: ImprovementPriority
  status: GapStatus
  bot_examples: BotMoment[]
  human_examples: HumanMoment[]
}

export interface RootCauseHit extends CallRef {
  description: string
  quote: string
  t: number
  better: string
}

export interface RootCause {
  pattern: string
  label: string
  area: string
  fix: string
  count: number
  of: number
  share: number
  /** From the share of bot calls affected, using the playbook's weak_share thresholds. */
  priority: ImprovementPriority
  calls: RootCauseHit[]
}

export interface MissedObjection extends CallRef {
  title: string
  quote: string
  t: number
  handling: string
  better: string
}

export interface ObjectionGap {
  type: string
  label: string
  total: number
  handled_well: number
  missed: MissedObjection[]
  human_example: (CallRef & { quote: string; t: number; handling: string }) | null
}

export interface CallIssue {
  kind: 'failure' | 'objection' | 'weak_score' | 'unanswered'
  title: string
  detail: string
  quote: string
  /** Seconds into the call; -1 when unknown. */
  t: number
  better: string
}

export interface CallRca extends CallRef {
  duration_s: number | null
  review_score: number | null
  outcome: string | null
  mood_end: string | null
  one_liner: string
  main_issue: string
  issue_count: number
  issues: CallIssue[]
}

export interface Improvement {
  verdict: Verdict
  parameters: ImprovementParameter[]
  root_causes: RootCause[]
  objections: ObjectionGap[]
  call_rca: CallRca[]
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
  area: string
  change: string
  rationale: string
  /** The new line or behaviour for the bot ("" when not a line). */
  bot_line: string
  /** Bot calls that show the problem (ids checked by the backend). */
  examples: CallRef[]
}

export interface Synthesis {
  verdict_headline: string
  verdict_detail: string
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
  /** Bot calls reviewed with an older analysis prompt (missing "better" lines). */
  outdated_bot_reviews: number
  records: PerSide<RecordCounts>
  sample_warning: string | null
  scores: PerSide<SideScore>
  dimensions: DimensionRow[]
  metrics: PairRow[]
  outcomes: PairRow[]
  signals: PerSide<SideSignals>
  improvement: Improvement
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
