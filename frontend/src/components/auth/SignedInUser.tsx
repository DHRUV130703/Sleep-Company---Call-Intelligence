import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { LogOut } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { authApi } from '@/lib/api-auth'

/** Top-bar: who is signed in, and a sign-out button. Hidden when sign-in is off (local use). */
export function SignedInUser() {
  const qc = useQueryClient()
  const status = useQuery({ queryKey: ['auth'], queryFn: authApi.status, staleTime: Infinity })
  const signOut = useMutation({
    mutationFn: authApi.logout,
    onSettled: () => qc.resetQueries(), // re-checks sign-in (→ sign-in screen) and forgets loaded data
  })
  const email = status.data?.email
  if (!email) return null
  return (
    <div className="flex items-center gap-1.5">
      <span className="hidden max-w-56 truncate text-[13px] text-muted-foreground md:inline" title={email}>
        {email}
      </span>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button variant="outline" size="icon" onClick={() => signOut.mutate()} disabled={signOut.isPending} aria-label={`Sign out ${email}`}>
            <LogOut className="size-[18px]" aria-hidden />
          </Button>
        </TooltipTrigger>
        <TooltipContent>Sign out</TooltipContent>
      </Tooltip>
    </div>
  )
}
