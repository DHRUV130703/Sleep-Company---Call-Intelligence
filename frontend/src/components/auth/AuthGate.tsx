import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AudioLines, Loader2 } from 'lucide-react'
import { type FormEvent, type ReactNode, useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { authApi, SIGNED_OUT_EVENT } from '@/lib/api-auth'
import { PRODUCT_AUTHOR, WORKSPACE_NAME, WORKSPACE_SUBTITLE } from '@/lib/constants'

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
  if (status.data?.required && !status.data.authenticated) return <SignIn />
  return <>{children}</>
}

function SignIn() {
  const qc = useQueryClient()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const login = useMutation({
    mutationFn: () => authApi.login(email, password),
    // Reset every query (not clear: clearing would also drop the sign-in check this screen waits on),
    // so the sign-in status is fetched again and pages load fresh data as the signed-in person.
    onSuccess: () => qc.resetQueries(),
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (email && password) login.mutate()
  }

  return (
    <main className="grid min-h-dvh place-items-center bg-background px-4">
      <form onSubmit={submit} className="w-full max-w-sm space-y-6 rounded-2xl border bg-surface p-8 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="grid size-11 place-items-center rounded-lg bg-foreground text-background">
            <AudioLines className="size-5" aria-hidden />
          </div>
          <div>
            <div className="text-lg leading-tight font-semibold">{WORKSPACE_NAME}</div>
            <div className="text-sm text-muted-foreground">{WORKSPACE_SUBTITLE}</div>
          </div>
        </div>
        <div className="space-y-4">
          <div className="space-y-2">
            <label htmlFor="signin-email" className="text-sm font-medium">
              Work email
            </label>
            <Input
              id="signin-email"
              type="email"
              autoComplete="username"
              autoFocus
              placeholder="name@thesleepcompany.in"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="h-10"
            />
          </div>
          <div className="space-y-2">
            <label htmlFor="signin-password" className="text-sm font-medium">
              Password
            </label>
            <Input
              id="signin-password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="h-10"
            />
          </div>
          <div aria-live="polite" className="min-h-5 text-sm text-negative">
            {login.isError && login.error.message}
          </div>
        </div>
        <Button type="submit" className="h-10 w-full" disabled={!email || !password || login.isPending}>
          {login.isPending && <Loader2 className="size-4 animate-spin motion-reduce:animate-none" aria-hidden />}
          Sign in
        </Button>
        <p className="text-center text-sm text-muted-foreground">
          Product by <span className="font-semibold text-foreground">{PRODUCT_AUTHOR}</span>
        </p>
      </form>
    </main>
  )
}
