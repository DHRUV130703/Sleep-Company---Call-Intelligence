import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { type ReactNode, useEffect } from 'react'
import { authApi, SIGNED_OUT_EVENT } from '@/lib/api-auth'
import { SignInScreen } from './SignInScreen'

/** Shows the sign-in screen when the server needs a signed-in person; otherwise renders the app. */
export function AuthGate({ children }: { children: ReactNode }) {
  const qc = useQueryClient()
  const status = useQuery({ queryKey: ['auth'], queryFn: authApi.status, staleTime: Infinity, retry: 1 })

  useEffect(() => {
    const onSignedOut = () => qc.invalidateQueries({ queryKey: ['auth'] })
    window.addEventListener(SIGNED_OUT_EVENT, onSignedOut)
    return () => window.removeEventListener(SIGNED_OUT_EVENT, onSignedOut)
  }, [qc])

  if (status.isPending) {
    return (
      <div className="grid min-h-dvh place-items-center" role="status" aria-label="Loading">
        <Loader2 className="size-6 animate-spin text-muted-foreground motion-reduce:animate-none" aria-hidden />
      </div>
    )
  }
  // If the status check itself fails (server down), show the app: its pages explain the error.
  if (status.data?.required && !status.data.authenticated) return <SignInScreen />
  return <>{children}</>
}
