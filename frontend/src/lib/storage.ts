// localStorage helpers for small per-browser preferences (theme, sidebar, table columns).
// Storage can be blocked (private mode, strict settings), so every access is wrapped.

export function readPref<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(`limezip:${key}`)
    return raw === null ? fallback : (JSON.parse(raw) as T)
  } catch {
    return fallback
  }
}

export function writePref<T>(key: string, value: T): void {
  try {
    localStorage.setItem(`limezip:${key}`, JSON.stringify(value))
  } catch {
    /* ignore — preferences are a convenience */
  }
}
