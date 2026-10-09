// "Download" menu on the AI vs Human page. Every download is also saved on the server (file in the
// database + public link); "Share links" saves all formats at once and lists their links to copy.

import { useMutation } from '@tanstack/react-query'
import { Check, ChevronDown, Copy, Download, FileJson, FileSpreadsheet, FileText, Link2, Sheet } from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { compareApi } from '@/lib/api-compare'
import type { CompareScope, ReportFormat, SavedReport } from '@/lib/types-compare'

const FORMAT_LABEL: Record<ReportFormat, string> = {
  pdf: 'PDF',
  docx: 'Word',
  xlsx: 'Excel',
  csv: 'CSV (scores per call)',
  json: 'JSON (all results)',
}

export function DownloadMenu({ scope }: { scope: CompareScope }) {
  return (
    <div className="flex gap-2">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline">
            <Download className="size-4" aria-hidden />
            Download
            <ChevronDown className="size-4 opacity-60" aria-hidden />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-72">
          <DropdownMenuLabel className="text-xs text-muted-foreground">Full report — to share with teams</DropdownMenuLabel>
          <Item scope={scope} kind="pdf" icon={FileText} title="PDF (.pdf)" hint="Ready to print or email" />
          <Item scope={scope} kind="docx" icon={FileText} title="Word document (.docx)" hint="Editable, opens in Word / Google Docs" />
          <Item scope={scope} kind="xlsx" icon={Sheet} title="Excel workbook (.xlsx)" hint="One sheet per part, ready to filter" />
          <DropdownMenuSeparator />
          <DropdownMenuLabel className="text-xs text-muted-foreground">Data</DropdownMenuLabel>
          <Item scope={scope} kind="csv" icon={FileSpreadsheet} title="Scores per call (CSV)" />
          <Item scope={scope} kind="json" icon={FileJson} title="All results (JSON)" />
          <DropdownMenuSeparator />
          <p className="px-2 py-1.5 text-xs text-muted-foreground">Every download is also saved with a public link.</p>
        </DropdownMenuContent>
      </DropdownMenu>
      <ShareLinks scope={scope} />
    </div>
  )
}

function Item({ scope, kind, icon: Icon, title, hint }: { scope: CompareScope; kind: ReportFormat; icon: typeof FileText; title: string; hint?: string }) {
  return (
    <DropdownMenuItem asChild>
      <a href={compareApi.exportUrl(scope, kind)} download>
        <Icon className="size-4" aria-hidden />
        <span className="flex flex-col">
          <span>{title}</span>
          {hint && <span className="text-xs text-muted-foreground">{hint}</span>}
        </span>
      </a>
    </DropdownMenuItem>
  )
}

/** Saves the report in every format and lists the public links, each with a copy button. */
function ShareLinks({ scope }: { scope: CompareScope }) {
  const save = useMutation({ mutationFn: () => compareApi.saveAll(scope) })
  return (
    <Popover onOpenChange={(open) => open && save.mutate()}>
      <PopoverTrigger asChild>
        <Button variant="outline">
          <Link2 className="size-4" aria-hidden />
          Share links
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-[min(30rem,calc(100vw-2rem))]">
        <h4 className="font-medium">Public report links</h4>
        <p className="mt-0.5 mb-3 text-xs text-muted-foreground">
          Stored in the database. Anyone with a link can open it — share them with care.
        </p>
        <div aria-live="polite">
          {save.isPending && <p className="text-muted-foreground">Saving the report in every format…</p>}
          {save.isError && <p className="text-negative">{save.error.message}</p>}
          {save.data && (
            <ul className="space-y-2">
              {save.data.reports.map((r) => (
                <LinkRow key={r.id} report={r} />
              ))}
            </ul>
          )}
        </div>
      </PopoverContent>
    </Popover>
  )
}

function LinkRow({ report }: { report: SavedReport }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(report.url)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      window.prompt('Copy this link:', report.url)
    }
  }
  return (
    <li className="flex items-center gap-2">
      <span className="w-36 shrink-0 text-[13px] font-medium">{FORMAT_LABEL[report.format]}</span>
      <a href={report.url} target="_blank" rel="noopener" className="min-w-0 flex-1 truncate font-mono text-xs text-muted-foreground underline-offset-4 hover:underline">
        {report.url}
      </a>
      <Button variant="ghost" size="icon" className="size-7 shrink-0" onClick={copy} aria-label={`Copy ${FORMAT_LABEL[report.format]} link`}>
        {copied ? <Check className="size-3.5 text-positive" aria-hidden /> : <Copy className="size-3.5" aria-hidden />}
      </Button>
    </li>
  )
}
