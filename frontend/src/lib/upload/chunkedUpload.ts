// Chunked, resumable file upload (PRD §6.1.3). One FileUpload per file.
//
// States: waiting → uploading ⇄ paused → verifying → done | failed
//
// - The file is sent in 8 MB chunks, 3 at a time. Each chunk carries its SHA-256 so the server can
//   reject damaged chunks. Failed chunks are retried with backoff (1s, 2s, 4s, 8s).
// - The server tells us which chunks it already has, so a paused upload — or the same file added
//   again after a page refresh — continues where it stopped instead of starting over.

import { ApiError, request } from '@/lib/api'
import { readPref, writePref } from '@/lib/storage'

export type UploadStatus = 'waiting' | 'uploading' | 'paused' | 'verifying' | 'done' | 'failed'

export interface UploadSnapshot {
  status: UploadStatus
  sentBytes: number
  totalBytes: number
  bytesPerSec: number
  etaSec: number | null
  uploadId: string | null
  resumed: boolean
  error: string | null
}

interface ServerUpload {
  upload_id: string
  chunk_size: number
  total_chunks: number
  received: number[]
  status: string
}

const PARALLEL = 3
const MAX_TRIES = 5

const fingerprint = (f: File) => `upload:${f.name}:${f.size}:${f.lastModified}`

async function sha256Hex(data: ArrayBuffer): Promise<string | null> {
  if (!crypto?.subtle) return null // only available on https/localhost
  const digest = await crypto.subtle.digest('SHA-256', data)
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, '0')).join('')
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

export class FileUpload {
  readonly file: File
  private state: UploadSnapshot
  private listeners = new Set<() => void>()
  private abort: AbortController | null = null
  private speedSamples: { t: number; bytes: number }[] = []

  constructor(file: File) {
    this.file = file
    this.state = {
      status: 'waiting', sentBytes: 0, totalBytes: file.size, bytesPerSec: 0, etaSec: null,
      uploadId: null, resumed: false, error: null,
    }
  }

  get snapshot(): UploadSnapshot {
    return this.state
  }

  subscribe(fn: () => void): () => void {
    this.listeners.add(fn)
    return () => this.listeners.delete(fn)
  }

  private set(patch: Partial<UploadSnapshot>) {
    this.state = { ...this.state, ...patch }
    this.listeners.forEach((fn) => fn())
  }

  pause() {
    if (this.state.status !== 'uploading') return
    this.abort?.abort()
    this.set({ status: 'paused', bytesPerSec: 0, etaSec: null })
  }

  async cancel() {
    this.abort?.abort()
    const id = this.state.uploadId
    writePref(fingerprint(this.file), null)
    this.set({ status: 'failed', error: 'Cancelled' })
    if (id) await request(`/uploads/${id}`, { method: 'DELETE' }).catch(() => undefined)
  }

  /** Start, or continue after pause / failure / page refresh. */
  async start(): Promise<void> {
    if (this.state.status === 'uploading' || this.state.status === 'verifying' || this.state.status === 'done') return
    this.abort = new AbortController()
    const signal = this.abort.signal
    this.set({ status: 'uploading', error: null })
    try {
      const server = await this.openUpload()
      if (signal.aborted) return
      const missing = [...Array(server.total_chunks).keys()].filter((i) => !server.received.includes(i))
      const doneBytes = server.received.reduce((sum, i) => sum + this.chunkLength(server, i), 0)
      this.set({ sentBytes: doneBytes, resumed: server.received.length > 0 })

      // Upload missing chunks with PARALLEL workers pulling from one queue.
      const queue = [...missing]
      const worker = async () => {
        while (queue.length && !signal.aborted) {
          const index = queue.shift()!
          await this.sendChunk(server, index, signal)
        }
      }
      await Promise.all(Array.from({ length: Math.min(PARALLEL, queue.length || 1) }, worker))
      if (signal.aborted) return

      this.set({ status: 'verifying', bytesPerSec: 0, etaSec: null })
      await request(`/uploads/${server.upload_id}/complete`, { method: 'POST' })
      writePref(fingerprint(this.file), null)
      this.set({ status: 'done', sentBytes: this.file.size })
    } catch (err) {
      if (signal.aborted) return
      this.set({ status: 'failed', error: err instanceof Error ? err.message : 'Upload failed' })
    }
  }

  private chunkLength(s: ServerUpload, i: number) {
    return Math.min(s.chunk_size, this.file.size - i * s.chunk_size)
  }

  private async openUpload(): Promise<ServerUpload> {
    const saved = readPref<string | null>(fingerprint(this.file), null) ?? this.state.uploadId
    if (saved) {
      try {
        const existing = await request<ServerUpload>(`/uploads/${saved}`)
        if (existing.status !== 'failed') {
          this.set({ uploadId: existing.upload_id })
          return existing
        }
      } catch {
        /* expired or deleted on the server → start fresh */
      }
    }
    const created = await request<ServerUpload>('/uploads', {
      method: 'POST',
      body: JSON.stringify({ filename: this.file.name, size: this.file.size, mime: this.file.type }),
    })
    writePref(fingerprint(this.file), created.upload_id)
    this.set({ uploadId: created.upload_id })
    return created
  }

  private async sendChunk(s: ServerUpload, index: number, signal: AbortSignal) {
    const start = index * s.chunk_size
    const blob = this.file.slice(start, start + this.chunkLength(s, index))
    const data = await blob.arrayBuffer()
    const hash = await sha256Hex(data)
    for (let attempt = 1; ; attempt++) {
      try {
        const res = await fetch(`/api/uploads/${s.upload_id}/chunks/${index}`, {
          method: 'PUT',
          body: data,
          signal,
          headers: hash ? { 'X-Chunk-SHA256': hash } : {},
        })
        if (!res.ok) {
          const body = await res.json().catch(() => ({}))
          throw new ApiError(res.status, body?.error?.code ?? 'HTTP_ERROR', body?.error?.message ?? `HTTP ${res.status}`)
        }
        this.addProgress(data.byteLength)
        return
      } catch (err) {
        if (signal.aborted) throw err
        const permanent = err instanceof ApiError && err.status >= 400 && err.status < 500 && err.status !== 429
        if (permanent || attempt >= MAX_TRIES) throw err
        await sleep(1000 * 2 ** (attempt - 1))
      }
    }
  }

  private addProgress(bytes: number) {
    const now = performance.now()
    const sent = this.state.sentBytes + bytes
    this.speedSamples.push({ t: now, bytes: sent })
    this.speedSamples = this.speedSamples.filter((s) => now - s.t < 5000) // speed over the last 5 s
    const first = this.speedSamples[0]
    const secs = (now - first.t) / 1000
    const speed = secs > 0.2 ? (sent - first.bytes) / secs : this.state.bytesPerSec
    this.set({
      sentBytes: sent,
      bytesPerSec: speed,
      etaSec: speed > 0 ? Math.round((this.file.size - sent) / speed) : null,
    })
  }
}
