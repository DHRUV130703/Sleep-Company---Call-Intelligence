// Number display for the AI vs Human report. The backend already rounds; this keeps display consistent.

/** 3 → "3", 2.45 → "2.5", null → "—". */
export function formatValue(n: number | null | undefined, suffix = ''): string {
  if (n === null || n === undefined) return '—'
  const rounded = Math.round(n * 10) / 10
  return `${rounded}${suffix}`
}
