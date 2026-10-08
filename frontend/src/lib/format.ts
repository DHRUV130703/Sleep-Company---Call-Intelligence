// Display helpers. All numbers shown to users go through these so formatting is consistent.

/** 523_440 s → "145 hours 24 mins" (matches the reference KPI pill). */
export function formatHoursMins(totalSeconds: number): string {
  const totalMins = Math.floor(totalSeconds / 60)
  const h = Math.floor(totalMins / 60)
  const m = totalMins % 60
  const hours = `${h} ${h === 1 ? 'hour' : 'hours'}`
  const mins = `${m} ${m === 1 ? 'min' : 'mins'}`
  return h > 0 ? `${hours} ${mins}` : mins
}

/** 93 → "1:33", 3725 → "1:02:05" */
export function formatClock(seconds: number): string {
  const s = Math.max(0, Math.round(seconds))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = String(s % 60).padStart(2, '0')
  return h > 0 ? `${h}:${String(m).padStart(2, '0')}:${sec}` : `${m}:${sec}`
}

/** "Oct 07, 2026 15:55" in the viewer's local time. */
export function formatDateTime(iso: string): string {
  const d = new Date(iso)
  const date = d.toLocaleDateString('en-US', { month: 'short', day: '2-digit', year: 'numeric' })
  const time = d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
  return `${date} ${time}`
}

/** "price" → "Price", "lack_of_interest" → "Lack of interest" */
export function humanize(key: string): string {
  const s = key.replace(/_/g, ' ')
  return s.charAt(0).toUpperCase() + s.slice(1)
}

/** "2026-10-08" → "Oct 08, 2026" — a calendar day, no timezone shift. */
export function formatDay(iso: string): string {
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso)
  return d.toLocaleDateString('en-US', { month: 'short', day: '2-digit', year: 'numeric' })
}
