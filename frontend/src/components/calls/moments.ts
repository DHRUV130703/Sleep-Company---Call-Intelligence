// Key-moment colours, shared by the waveform markers and the Key moments list.
// Colour is never the only signal: markers and list rows always carry the moment's label too.

export type MarkerTone = 'positive' | 'negative' | 'warning' | 'ai' | 'muted'

export const MOMENT_TONE: Record<string, MarkerTone> = {
  commitment: 'positive',
  callback_agreed: 'positive',
  objection: 'negative',
  refusal: 'negative',
  escalation: 'negative',
  price_asked: 'warning',
  question_unanswered: 'warning',
  other: 'muted',
}

/** Tailwind background class per tone (tokens only). */
export const TONE_BG: Record<MarkerTone, string> = {
  positive: 'bg-positive',
  negative: 'bg-negative',
  warning: 'bg-warning',
  ai: 'bg-ai',
  muted: 'bg-muted-foreground',
}
