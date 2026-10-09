// "Download" menu on the AI vs Human page: share the full report (Word / PDF) or the raw data (CSV / JSON).
// Word comes ready-made from the server. PDF opens a print-ready page and the browser's "Save as PDF"
// dialog — browsers render Hindi quotes correctly, which server-made PDFs often don't.

import { ChevronDown, Download, FileJson, FileSpreadsheet, FileText, Printer } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { compareApi } from '@/lib/api-compare'
import type { CompareScope } from '@/lib/types-compare'

export function DownloadMenu({ scope }: { scope: CompareScope }) {
  return (
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
        <DropdownMenuItem asChild>
          <a href={compareApi.exportUrl(scope, 'docx')} download>
            <FileText className="size-4" aria-hidden />
            <span className="flex flex-col">
              <span>Word document (.docx)</span>
              <span className="text-xs text-muted-foreground">Editable, opens in Word / Google Docs</span>
            </span>
          </a>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <a href={compareApi.reportUrl(scope)} target="_blank" rel="noopener">
            <Printer className="size-4" aria-hidden />
            <span className="flex flex-col">
              <span>PDF</span>
              <span className="text-xs text-muted-foreground">Opens the report — choose “Save as PDF”</span>
            </span>
          </a>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuLabel className="text-xs text-muted-foreground">Data</DropdownMenuLabel>
        <DropdownMenuItem asChild>
          <a href={compareApi.exportUrl(scope, 'csv')} download>
            <FileSpreadsheet className="size-4" aria-hidden />
            Scores per call (CSV)
          </a>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <a href={compareApi.exportUrl(scope, 'json')} download>
            <FileJson className="size-4" aria-hidden />
            All results (JSON)
          </a>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
