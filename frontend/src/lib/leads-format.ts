// Small display + export helpers used by the leads screens.

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** "2026-10-08" (or a full ISO datetime) → "08 Oct '26". Date-only strings are read as local days. */
export function formatShortDate(value: string): string {
  const d = /^\d{4}-\d{2}-\d{2}$/.test(value) ? new Date(`${value}T00:00:00`) : new Date(value)
  if (Number.isNaN(d.getTime())) return value
  const day = String(d.getDate()).padStart(2, '0')
  const year = String(d.getFullYear()).slice(-2)
  return `${day} ${MONTHS[d.getMonth()]} '${year}`
}

/** "Priya Sharma" → "PS", "Voice Bot v1" → "VB". */
export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return '?'
  return parts
    .slice(0, 2)
    .map((p) => p.charAt(0).toUpperCase())
    .join('')
}

/** Today as "YYYY-MM-DD" in local time, `offsetDays` from now. Used by date inputs. */
export function isoDay(offsetDays = 0): string {
  const d = new Date()
  d.setDate(d.getDate() + offsetDays)
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

/** Turn rows into CSV text. Cells are quoted so commas and quotes in names are safe. */
export function toCsv(header: string[], rows: (string | number)[][]): string {
  const cell = (v: string | number) => `"${String(v).replace(/"/g, '""')}"`
  return [header, ...rows].map((r) => r.map(cell).join(',')).join('\r\n')
}

/** Save text as a file in the browser (no server round-trip). */
export function downloadText(filename: string, text: string, type = 'text/csv;charset=utf-8'): void {
  const url = URL.createObjectURL(new Blob([text], { type }))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
