// "Download" menu on the AI vs Human page. (Each download is also kept on the server, in the `reports` table.)

import { ChevronDown, Download, FileJson, FileSpreadsheet, FileText, Sheet } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { compareApi } from '@/lib/api-compare'
import type { CompareScope, ReportFormat } from '@/lib/types-compare'

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
      <DropdownMenuContent align="end" className="w-52">
        <Item scope={scope} kind="pdf" icon={FileText} title="PDF" />
        <Item scope={scope} kind="docx" icon={FileText} title="Word" />
        <Item scope={scope} kind="xlsx" icon={Sheet} title="Excel" />
        <DropdownMenuSeparator />
        <Item scope={scope} kind="csv" icon={FileSpreadsheet} title="CSV" hint="scores per call" />
        <Item scope={scope} kind="json" icon={FileJson} title="JSON" hint="raw data" />
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

interface ItemProps {
  scope: CompareScope
  kind: ReportFormat
  icon: typeof FileText
  title: string
  hint?: string
}

function Item({ scope, kind, icon: Icon, title, hint }: ItemProps) {
  return (
    <DropdownMenuItem asChild>
      <a href={compareApi.exportUrl(scope, kind)} download>
        <Icon className="size-4" aria-hidden />
        {title}
        {hint && <span className="ml-auto text-xs text-muted-foreground">{hint}</span>}
      </a>
    </DropdownMenuItem>
  )
}
