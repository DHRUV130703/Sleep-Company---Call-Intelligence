import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronDown, Layers, LogOut } from 'lucide-react'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { authApi } from '@/lib/api-auth'

/** "dhruv.gohil@…" → "Dhruv Gohil", "dhruv123" → "Dhruv123" (the part before any @, split on dots, dashes and underscores). */
function displayName(email: string): string {
  return email
    .split('@')[0]
    .split(/[._-]+/)
    .filter(Boolean)
    .map((w) => w[0].toUpperCase() + w.slice(1))
    .join(' ')
}

function initials(name: string): string {
  const parts = name.split(' ')
  return ((parts[0]?.[0] ?? '') + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase() || '?'
}

function workspaceLabel(workspace: string): string {
  return workspace === 'main' ? 'Main workspace' : `${workspace[0].toUpperCase()}${workspace.slice(1)}'s workspace`
}

/** Top-bar account button: who is signed in and their workspace; the menu has Sign out. Hidden when sign-in is off. */
export function SignedInUser() {
  const qc = useQueryClient()
  const status = useQuery({ queryKey: ['auth'], queryFn: authApi.status, staleTime: Infinity })
  const signOut = useMutation({
    mutationFn: authApi.logout,
    onSettled: () => qc.resetQueries(), // re-checks sign-in (→ sign-in screen) and forgets loaded data
  })
  const email = status.data?.email
  if (!email) return null
  const name = displayName(email)
  const workspace = workspaceLabel(status.data?.workspace ?? 'main')

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label={`Account: ${email}, ${workspace}`}
          className="flex h-10 items-center gap-2.5 rounded-lg border bg-surface py-1 pr-2 pl-1 transition-colors hover:bg-accent focus-visible:outline-2 focus-visible:outline-ring"
        >
          <span className="grid size-8 shrink-0 place-items-center rounded-md bg-ai-soft text-[13px] font-semibold text-ai" aria-hidden>
            {initials(name)}
          </span>
          <span className="hidden min-w-0 text-left leading-tight md:block">
            <span className="block max-w-40 truncate text-[13px] font-medium">{name}</span>
            <span className="block max-w-40 truncate text-xs text-muted-foreground">{workspace}</span>
          </span>
          <ChevronDown className="size-4 text-muted-foreground" aria-hidden />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        <DropdownMenuLabel className="font-normal">
          <div className="text-sm font-medium">{name}</div>
          {email.includes('@') && <div className="truncate text-xs text-muted-foreground">{email}</div>}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <div className="flex items-start gap-2 px-2 py-1.5 text-sm">
          <Layers className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
          <div>
            <div>{workspace}</div>
            <div className="text-xs text-muted-foreground">You only see this workspace's calls and reports.</div>
          </div>
        </div>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => signOut.mutate()} disabled={signOut.isPending}>
          <LogOut className="size-4" aria-hidden />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
