import { CircleCheck, FileAudio, FolderArchive, Pause, Play, RotateCcw, Upload, X } from 'lucide-react'
import { useRef, useState, useSyncExternalStore } from 'react'
import { Button } from '@/components/ui/button'
import { formatClock } from '@/lib/format'
import type { FileUpload } from '@/lib/upload/chunkedUpload'
import { ACCEPT, formatBytes } from '@/lib/upload/helpers'
import { cn } from '@/lib/utils'

export interface FileItem {
  upload: FileUpload
  agentType: 'ai' | 'human' | ''
}

interface Props {
  items: FileItem[]
  mixed: boolean
  onAdd: (files: File[]) => void
  onChange: (items: FileItem[]) => void
}

export function FilesPanel({ items, mixed, onAdd, onChange }: Props) {
  const input = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  const drop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    onAdd(Array.from(e.dataTransfer.files))
  }

  return (
    <div className="space-y-4">
      <div
        role="button"
        tabIndex={0}
        aria-label="Add recordings: drop files here or press Enter to browse"
        onClick={() => input.current?.click()}
        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={drop}
        className={cn(
          'flex cursor-pointer flex-col items-center rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors',
          'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring',
          dragging ? 'border-ai bg-ai-soft' : 'border-border bg-surface hover:bg-surface-sunken/60',
        )}
      >
        <div className="mb-3 grid size-11 place-items-center rounded-full bg-surface-sunken">
          <Upload className="size-5" aria-hidden />
        </div>
        <p className="font-medium">{dragging ? 'Release to add' : 'Drop a ZIP or audio/video files here'}</p>
        <p className="mt-1 text-xs text-muted-foreground">
          or <span className="underline">browse files</span> · mp3 wav m4a mp4 aac ogg amr … up to 2 GB each, ZIP up to 5 GB
        </p>
        <input
          ref={input}
          type="file"
          multiple
          accept={ACCEPT}
          className="hidden"
          onChange={(e) => {
            onAdd(Array.from(e.target.files ?? []))
            e.target.value = ''
          }}
        />
      </div>
      <p className="text-xs text-muted-foreground">
        Uploads start right away and continue if your connection drops. If you refresh the page, add the same file
        again and it picks up where it stopped. A ZIP can include a <code className="font-mono">manifest.csv</code>{' '}
        (file, phone, customer name, agent type…) to fill in call details.
      </p>

      {items.length > 0 && (
        <ul className="divide-y rounded-xl border bg-surface">
          {items.map((item, i) => (
            <FileRow
              key={`${item.upload.file.name}-${item.upload.file.lastModified}-${i}`}
              item={item}
              mixed={mixed}
              onAgentType={(agentType) => onChange(items.map((x, j) => (j === i ? { ...x, agentType } : x)))}
              onRemove={() => {
                void item.upload.cancel()
                onChange(items.filter((_, j) => j !== i))
              }}
            />
          ))}
        </ul>
      )}
    </div>
  )
}

function FileRow({ item, mixed, onAgentType, onRemove }: {
  item: FileItem
  mixed: boolean
  onAgentType: (v: 'ai' | 'human' | '') => void
  onRemove: () => void
}) {
  const up = item.upload
  const s = useSyncExternalStore((cb) => up.subscribe(cb), () => up.snapshot)
  const pct = s.totalBytes ? Math.round((100 * s.sentBytes) / s.totalBytes) : 0
  const isZip = up.file.name.toLowerCase().endsWith('.zip')
  const Icon = isZip ? FolderArchive : FileAudio

  return (
    <li className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3">
      <Icon className="size-5 shrink-0 text-muted-foreground" aria-hidden />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-3">
          <span className="truncate font-medium" title={up.file.name}>{up.file.name}</span>
          <span className="num shrink-0 text-xs text-muted-foreground">{formatBytes(up.file.size)}</span>
        </div>
        <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-surface-sunken" aria-hidden>
          <div
            className={cn('h-full rounded-full transition-[width] duration-200 ease-out',
              s.status === 'failed' ? 'bg-negative' : s.status === 'done' ? 'bg-positive' : 'bg-ai')}
            style={{ width: `${pct}%` }}
          />
        </div>
        <div className="mt-1 text-xs text-muted-foreground" aria-live="polite">
          {s.status === 'uploading' && (
            <span className="num">
              {pct}% · {formatBytes(s.bytesPerSec)}/s{s.etaSec != null && ` · ${formatClock(s.etaSec)} left`}
              {s.resumed && ' · resumed'}
            </span>
          )}
          {s.status === 'waiting' && 'Waiting…'}
          {s.status === 'paused' && `Paused at ${pct}%`}
          {s.status === 'verifying' && 'Verifying…'}
          {s.status === 'done' && (
            <span className="inline-flex items-center gap-1 text-positive">
              <CircleCheck className="size-3.5" aria-hidden /> Uploaded and verified
            </span>
          )}
          {s.status === 'failed' && <span className="text-negative">{s.error}</span>}
        </div>
      </div>

      {mixed && (
        <select
          aria-label={`Agent type for ${up.file.name}`}
          value={item.agentType}
          onChange={(e) => onAgentType(e.target.value as FileItem['agentType'])}
          className={cn('h-8 rounded-md border bg-surface px-2 text-xs',
            !item.agentType && !isZip && 'border-warning')}
        >
          <option value="">{isZip ? 'From manifest' : 'AI or Human?'}</option>
          <option value="ai">AI voice bot</option>
          <option value="human">Human agents</option>
        </select>
      )}

      <div className="flex items-center gap-1">
        {s.status === 'uploading' && (
          <Button variant="ghost" size="icon" aria-label={`Pause ${up.file.name}`} onClick={() => up.pause()}>
            <Pause className="size-4" />
          </Button>
        )}
        {s.status === 'paused' && (
          <Button variant="ghost" size="icon" aria-label={`Resume ${up.file.name}`} onClick={() => void up.start()}>
            <Play className="size-4" />
          </Button>
        )}
        {s.status === 'failed' && s.error !== 'Cancelled' && (
          <Button variant="ghost" size="icon" aria-label={`Retry ${up.file.name}`} onClick={() => void up.start()}>
            <RotateCcw className="size-4" />
          </Button>
        )}
        <Button variant="ghost" size="icon" aria-label={`Remove ${up.file.name}`} onClick={onRemove}>
          <X className="size-4" />
        </Button>
      </div>
    </li>
  )
}
