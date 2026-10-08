// Human-readable names for values that come from the API. One place, so every screen says the same thing.

export const OUTCOME_LABELS: Record<string, string> = {
  converted: 'Converted',
  store_visit: 'Store visit',
  callback_scheduled: 'Callback scheduled',
  agreed_next_step: 'Agreed next step',
  follow_up_pending: 'Follow-up pending',
  not_interested: 'Not interested',
  not_qualified: 'Not qualified',
  no_outcome: 'No outcome',
}

export const LEAD_STATUS_LABELS: Record<string, string> = {
  follow_up_pending: 'Follow Up Pending',
  callback_scheduled: 'Callback Scheduled',
  store_visit_planned: 'Store Visit Planned',
  won: 'Won',
  lost: 'Lost',
  not_qualified: 'Not Qualified',
}

export const INTENT_LABELS: Record<string, string> = {
  high: 'High Intent',
  moderate: 'Moderate Intent',
  neutral: 'Neutral Intent',
  low: 'Low Intent',
  not_qualified: 'Not Qualified',
  not_available: 'Not Available',
}

/** Tailwind classes per intent bucket (text + soft background). */
export const INTENT_STYLES: Record<string, string> = {
  high: 'text-intent-high bg-positive-soft',
  moderate: 'text-intent-moderate bg-intent-moderate/10',
  neutral: 'text-intent-neutral bg-surface-sunken',
  low: 'text-intent-low bg-negative-soft',
  not_qualified: 'text-muted-foreground bg-surface-sunken',
  not_available: 'text-muted-foreground bg-surface-sunken',
}

export const STAGE_LABELS: Record<string, string> = {
  queued: 'Queued',
  downloading: 'Downloading',
  preparing: 'Preparing audio',
  transcribing: 'Transcribing',
  analysing: 'Analysing',
  done: 'Done',
}

export const MOOD_EMOJI: Record<string, string> = { positive: '🙂', neutral: '😐', negative: '🙁' }
