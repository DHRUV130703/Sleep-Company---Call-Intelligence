// API response types for All Conversations and Lead Details — mirror backend/app/api/leads.py.

export type AgentType = 'ai' | 'human'

/** Fields shared by every lead row (backend `lead_row`). */
export interface LeadBase {
  id: number
  name: string
  has_name: boolean
  phone: string
  owner: string
  assignee: string
  status: string
  status_category: 'won' | 'lost' | 'in_progress'
  intent_score: number | null
  intent_bucket: string | null
  last_call_at: string | null
}

export interface NextTask {
  title: string
  due_date: string | null
}

/** One row of the leads table. A lead is one phone number; `conversations` counts its recordings. */
export interface LeadListItem extends LeadBase {
  conversations: number
  agent_types: AgentType[]
  next_task: NextTask | null
  processing: boolean
}

export interface LeadListResponse {
  items: LeadListItem[]
  total: number
  page: number
  page_size: number
}

export interface IntentCounts {
  high: number
  moderate: number
  neutral: number
  low: number
  not_qualified: number
  not_available: number
}

export type IntentDeltas = { [K in keyof IntentCounts]: number | null }

export interface LeadKpis {
  conversations: number
  audio_seconds: number
  detailed_pct: number | null
  talk_listen_agent_pct: number | null
  quality_pct: number | null
  total_leads: number
  connected_leads: number
  not_connected_leads: number
  won: number
  lost: number
  in_progress: number
  intent: IntentCounts
  /** Percent change vs the previous equal-length period. Empty when there is no previous period. */
  deltas: Partial<Record<string, number | null>> & { intent?: IntentDeltas }
  has_previous_period: boolean
}

export interface FilterOptions {
  owners: string[]
  campaigns: string[]
  batches: { id: number; name: string }[]
  statuses: string[]
  intent_buckets: string[]
}

// ---------------------------------------------------------------------------
// Lead details
// ---------------------------------------------------------------------------

export interface CallSummary {
  one_liner?: string
  bullets?: string[]
}

export interface LeadCall {
  id: number
  batch_id: number
  label: string
  agent_type: AgentType
  agent_name: string | null
  campaign: string | null
  call_datetime: string | null
  duration_s: number | null
  stage: string
  status: string
  error_message: string | null
  outcome: string | null
  intent_score: number | null
  intent_bucket: string | null
  quality_pct: number | null
  language: string | null
  one_liner: string | null
  summary: CallSummary | null
}

export interface IntentInsight {
  score: number
  bucket: string
  positive_factors: string[]
  negative_factors: string[]
}

export type BantStatus = 'known' | 'partial' | 'unknown'

export interface BantItem {
  status: BantStatus
  value: string
  evidence: string
  verified: boolean
}

export interface Bant {
  budget: BantItem
  authority: BantItem
  need: BantItem
  timeline: BantItem
}

export interface Mood {
  start: string
  end: string
  trajectory: string
}

export interface CustomerDetails {
  name: string
  city: string
  pincode: string
  products_discussed: string[]
  size: string
  budget: string
  pain_points: string[]
  competitors_mentioned: string[]
}

export interface Objection {
  type: string
  title: string
  customer_quote: string
  t: number | null
  handling: string
  handled_well: boolean
  customer_satisfied: boolean
  better_response: string
  verified: boolean
  call_id: number
  call_label: string
}

export interface LeadInsights {
  intent: IntentInsight | null
  bant: Bant | null
  mood: Mood | null
  customer: CustomerDetails | null
  outcome: { disposition?: string; next_step?: string } | null
  unanswered_questions: string[]
  objections: Objection[]
}

export interface PathAction {
  title: string
  say: string
  why: string
  when: string
  due: string | null
}

export interface PathToConversion {
  bullets: string[]
  next_actions: PathAction[]
  based_on_calls: number
}

export interface LeadAction {
  id: number
  call_id: number | null
  title: string
  say: string
  why: string
  due_date: string | null
  done: boolean
  source: string
}

export interface LeadNote {
  id: number
  body: string
  created_at: string
}

export interface LeadDetail extends LeadBase {
  stats: {
    total_duration_s: number
    talk_listen_agent_pct: number | null
    intent_score: number | null
    avg_quality_pct: number | null
  }
  /** Newest first. */
  calls: LeadCall[]
  insights: LeadInsights
  path: PathToConversion | null
  actions: LeadAction[]
  notes: LeadNote[]
  statuses: string[]
}
