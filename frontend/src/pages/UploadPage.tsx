import { useMutation } from '@tanstack/react-query'
import { FileSpreadsheet, FolderArchive, Info, Link2, Loader2 } from 'lucide-react'
import { useCallback, useEffect, useState, useSyncExternalStore } from 'react'
import { useNavigate } from 'react-router'
import { PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { BatchOptions, type Options } from '@/components/upload/BatchOptions'
import { type FileItem, FilesPanel } from '@/components/upload/FilesPanel'
import { LinksPanel, type LinksState } from '@/components/upload/LinksPanel'
import { SheetPanel, type SheetState } from '@/components/upload/SheetPanel'
import { batchesApi } from '@/lib/api-batches'
import type { BatchCreate } from '@/lib/types-batches'
import { FileUpload } from '@/lib/upload/chunkedUpload'
import { ACCEPT, parseLinks } from '@/lib/upload/helpers'

type Source = 'files' | 'sheet' | 'links'
const EXTS = ACCEPT.split(',')

export default function UploadPage() {
  const navigate = useNavigate()
  const [source, setSource] = useState<Source>('sheet')
  const [options, setOptions] = useState<Options>({ mode: 'human', name: '', campaign: '', script: 'roman' })
  const [files, setFiles] = useState<FileItem[]>([])
  const [sheet, setSheet] = useState<SheetState>({ preview: null, mapping: {} })
  const [sheetOk, setSheetOk] = useState(false)
  const [links, setLinks] = useState<LinksState>({ single: '', ai: '', human: '' })
  const mixed = options.mode === 'column'

  const addFiles = (picked: File[]) => {
    const ok = picked.filter((f) => EXTS.some((ext) => f.name.toLowerCase().endsWith(ext)))
    const items = ok.map((f) => ({ upload: new FileUpload(f), agentType: '' as const }))
    setFiles((cur) => [...cur, ...items])
    items.forEach((i) => void i.upload.start()) // start immediately; the server dedupes and resumes
  }

  // Re-render when any upload changes state, so the submit button knows when all are done.
  const uploadsKey = useSyncExternalStore(
    useCallback((cb) => {
      const unsubs = files.map((f) => f.upload.subscribe(cb))
      return () => unsubs.forEach((u) => u())
    }, [files]),
    () => files.map((f) => f.upload.snapshot.status).join(','),
  )

  // Warn before leaving while files are still uploading.
  useEffect(() => {
    const busy = uploadsKey.split(',').some((s) => s === 'uploading' || s === 'verifying')
    if (!busy) return
    const warn = (e: BeforeUnloadEvent) => e.preventDefault()
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [uploadsKey])

  const onSheetCheck = useCallback((ok: boolean) => setSheetOk(ok), [])
  const { ready, reason } = readiness(source, options, files, sheet, sheetOk, links)

  const create = useMutation({
    mutationFn: () => batchesApi.create(buildRequest(source, options, files, sheet, links)),
    onSuccess: (batch) => navigate(`/batches/${batch.id}`),
  })

  return (
    <>
      <PageHeader
        title="Analyse calls"
        description="Add recordings from a spreadsheet of links, a ZIP or files. Every call is transcribed, summarised and scored."
      />
      <Card>
        <CardContent className="space-y-6">
          <Tabs value={source} onValueChange={(v) => setSource(v as Source)}>
            <TabsList className="mb-4">
              <TabsTrigger value="sheet"><FileSpreadsheet className="size-4" /> Spreadsheet</TabsTrigger>
              <TabsTrigger value="files"><FolderArchive className="size-4" /> Files / ZIP</TabsTrigger>
              <TabsTrigger value="links"><Link2 className="size-4" /> Links</TabsTrigger>
            </TabsList>
            <TabsContent value="sheet">
              <SheetPanel value={sheet} mode={options.mode} onChange={setSheet} onCheck={onSheetCheck} />
            </TabsContent>
            <TabsContent value="files">
              <FilesPanel items={files} mixed={mixed} onAdd={addFiles} onChange={setFiles} />
            </TabsContent>
            <TabsContent value="links">
              <LinksPanel value={links} mixed={mixed} onChange={setLinks} />
            </TabsContent>
          </Tabs>

          <BatchOptions value={options} onChange={setOptions} />

          <div className="flex flex-wrap items-center gap-3 border-t pt-5">
            <Button size="lg" disabled={!ready || create.isPending} onClick={() => create.mutate()}>
              {create.isPending && <Loader2 className="size-4 animate-spin" />}
              Transcribe and analyse
            </Button>
            <Button size="lg" variant="outline" onClick={() => navigate('/batches')}>
              Open saved results
            </Button>
            {!ready && reason && <span className="text-sm text-muted-foreground">{reason}</span>}
          </div>
          {create.isError && <p role="alert" className="text-negative">{create.error.message}</p>}

          <p className="flex gap-2 text-xs text-muted-foreground">
            <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />
            Everything runs on this computer: speech-to-text with Whisper and the insights with a local AI model
            (Ollama). Recordings and transcripts don't leave this machine.
          </p>
        </CardContent>
      </Card>
    </>
  )
}

function readiness(
  source: Source, o: Options, files: FileItem[], sheet: SheetState, sheetOk: boolean, links: LinksState,
): { ready: boolean; reason: string } {
  if (source === 'files') {
    if (!files.length) return { ready: false, reason: 'Add at least one file.' }
    const statuses = files.map((f) => f.upload.snapshot.status)
    if (statuses.some((s) => s !== 'done' && s !== 'failed')) return { ready: false, reason: 'Waiting for uploads to finish…' }
    if (!statuses.includes('done')) return { ready: false, reason: 'No file uploaded successfully.' }
    const missingType = files.some((f) => o.mode === 'column' && !f.agentType && !f.upload.file.name.toLowerCase().endsWith('.zip'))
    if (missingType) return { ready: false, reason: 'Choose AI or Human for each file.' }
    return { ready: true, reason: '' }
  }
  if (source === 'sheet') {
    if (!sheet.preview) return { ready: false, reason: 'Choose a spreadsheet.' }
    if (!sheet.mapping.recording_url) return { ready: false, reason: 'Pick the column with the recording links.' }
    if (o.mode === 'column' && !sheet.mapping.agent_type) return { ready: false, reason: 'Pick the agent type column, or choose AI / Human above.' }
    return sheetOk ? { ready: true, reason: '' } : { ready: false, reason: 'Checking rows…' }
  }
  const count = o.mode === 'column'
    ? parseLinks(links.ai).filter((l) => l.valid).length + parseLinks(links.human).filter((l) => l.valid).length
    : parseLinks(links.single).filter((l) => l.valid).length
  return count ? { ready: true, reason: '' } : { ready: false, reason: 'Paste at least one valid link.' }
}

function buildRequest(
  source: Source, o: Options, files: FileItem[], sheet: SheetState, links: LinksState,
): BatchCreate {
  const base: BatchCreate = { name: o.name, campaign: o.campaign, agent_type_mode: o.mode, transcript_script: o.script }
  if (source === 'files') {
    return {
      ...base,
      files: files
        .filter((f) => f.upload.snapshot.status === 'done' && f.upload.snapshot.uploadId)
        .map((f) => ({ upload_id: f.upload.snapshot.uploadId!, ...(f.agentType ? { agent_type: f.agentType } : {}) })),
    }
  }
  if (source === 'sheet') return { ...base, sheet: { sheet_id: sheet.preview!.sheet_id, mapping: sheet.mapping } }
  const toLinks = (text: string, agent_type?: 'ai' | 'human') =>
    parseLinks(text).filter((l) => l.valid).map((l) => ({ url: l.url, label: l.label, agent_type }))
  return {
    ...base,
    links: o.mode === 'column' ? [...toLinks(links.ai, 'ai'), ...toLinks(links.human, 'human')] : toLinks(links.single),
  }
}
