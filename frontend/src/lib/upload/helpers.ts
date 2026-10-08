// Small helpers for the Upload screen.

export const ACCEPT = '.zip,.mp3,.wav,.m4a,.mp4,.aac,.ogg,.opus,.webm,.flac,.amr,.mpeg,.3gp,.mov'

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(0)} KB`
  if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1)} MB`
  return `${(n / 1024 ** 3).toFixed(2)} GB`
}

export interface ParsedLink {
  url: string
  label?: string
  valid: boolean
}

/** One link per line, optionally "Label | https://…" (same format as the reference tool). */
export function parseLinks(text: string): ParsedLink[] {
  return text
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean)
    .map((line) => {
      const [label, url] = line.includes('|') ? line.split('|').map((x) => x.trim()) : [undefined, line]
      let valid = false
      try {
        const u = new URL(url)
        valid = u.protocol === 'http:' || u.protocol === 'https:'
      } catch {
        valid = false
      }
      return { url, label, valid }
    })
}
