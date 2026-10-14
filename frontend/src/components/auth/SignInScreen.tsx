import { useMutation, useQueryClient } from '@tanstack/react-query'
import { AudioLines, Eye, EyeOff, Loader2, Lock, Mail, TriangleAlert } from 'lucide-react'
import { type FormEvent, type ReactNode, useState } from 'react'
import { Button } from '@/components/ui/button'
import { authApi } from '@/lib/api-auth'
import { PRODUCT_AUTHOR, WORKSPACE_NAME, WORKSPACE_SUBTITLE } from '@/lib/constants'
import { cn } from '@/lib/utils'

const HIGHLIGHTS = [
  'Every call transcribed, summarised and scored',
  'Next steps and buying intent for each lead',
  'AI voice bot vs human agents, call by call',
]

/** Full-page sign-in: brand panel on the left (desktop only), the form on the right. */
export function SignInScreen() {
  return (
    <main className="grid min-h-dvh bg-background lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
      <BrandPanel />
      <div className="flex min-h-dvh flex-col px-6 py-10 sm:px-10">
        <div className="flex flex-1 items-center justify-center">
          <SignInForm />
        </div>
        <p className="text-center text-[15px] text-muted-foreground">
          Product by <span className="font-semibold text-foreground">{PRODUCT_AUTHOR}</span>
        </p>
      </div>
    </main>
  )
}

function Logo({ className }: { className?: string }) {
  return (
    <div className={cn('flex items-center gap-3', className)}>
      <div className="grid size-11 shrink-0 place-items-center rounded-xl bg-foreground text-background">
        <AudioLines className="size-5" aria-hidden />
      </div>
      <div>
        <div className="text-lg leading-tight font-semibold">{WORKSPACE_NAME}</div>
        <div className="text-sm text-muted-foreground">{WORKSPACE_SUBTITLE}</div>
      </div>
    </div>
  )
}

function BrandPanel() {
  return (
    <aside className="relative hidden overflow-hidden border-r bg-surface lg:flex lg:flex-col lg:justify-between lg:p-12">
      <Logo />
      <div className="relative z-10 max-w-md space-y-6">
        <h2 className="text-[32px] leading-tight font-semibold tracking-tight text-balance">
          Hear what every sales call is really saying.
        </h2>
        <ul className="space-y-3 text-[15px] text-muted-foreground">
          {HIGHLIGHTS.map((h) => (
            <li key={h} className="flex items-center gap-3">
              <span className="size-1.5 shrink-0 rounded-full bg-ai" aria-hidden />
              {h}
            </li>
          ))}
        </ul>
      </div>
      <Waveform />
    </aside>
  )
}

/** Decorative sound-wave bars along the bottom of the brand panel. */
function Waveform() {
  const bars = Array.from({ length: 48 }, (_, i) => 18 + Math.round(70 * Math.abs(Math.sin(i * 0.55) * Math.cos(i * 0.21))))
  return (
    <div className="flex h-24 w-full items-end justify-between opacity-60" aria-hidden>
      {bars.map((h, i) => (
        <span key={i} className="w-1.5 rounded-full bg-ai/40" style={{ height: `${h}%` }} />
      ))}
    </div>
  )
}

function SignInForm() {
  const qc = useQueryClient()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const login = useMutation({
    mutationFn: () => authApi.login(email, password),
    // Reset every query (not clear: clearing would also drop the sign-in check AuthGate waits on),
    // so the sign-in status is fetched again and pages load fresh data as the signed-in person.
    onSuccess: () => qc.resetQueries(),
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (email && password) login.mutate()
  }

  return (
    <form onSubmit={submit} className="w-full max-w-[400px] space-y-7" noValidate>
      <Logo className="lg:hidden" />
      <div className="space-y-1.5">
        <h1 className="text-2xl font-semibold tracking-tight">Sign in</h1>
        <p className="text-muted-foreground">Use your Sleep Company work account.</p>
      </div>

      <div className="space-y-4">
        <Field id="signin-email" label="Email address" icon={<Mail className="size-4" aria-hidden />}>
          <input
            id="signin-email"
            type="email"
            inputMode="email"
            autoComplete="username"
            autoFocus
            placeholder="Enter your email address"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={INPUT}
          />
        </Field>
        <Field
          id="signin-password"
          label="Password"
          icon={<Lock className="size-4" aria-hidden />}
          action={
            <button
              type="button"
              onClick={() => setShowPassword((s) => !s)}
              aria-label={showPassword ? 'Hide password' : 'Show password'}
              aria-pressed={showPassword}
              className="grid size-8 place-items-center rounded-md text-muted-foreground hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring"
            >
              {showPassword ? <EyeOff className="size-4" aria-hidden /> : <Eye className="size-4" aria-hidden />}
            </button>
          }
        >
          <input
            id="signin-password"
            type={showPassword ? 'text' : 'password'}
            autoComplete="current-password"
            placeholder="Enter your password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={cn(INPUT, 'pr-11')}
          />
        </Field>
      </div>

      <div aria-live="polite">
        {login.isError && (
          <p className="mb-4 flex items-start gap-2 rounded-lg bg-negative-soft px-3 py-2.5 text-sm text-negative">
            <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
            {login.error.message}
          </p>
        )}
        <Button type="submit" className="h-11 w-full text-[15px]" disabled={!email || !password || login.isPending}>
          {login.isPending && <Loader2 className="size-4 animate-spin motion-reduce:animate-none" aria-hidden />}
          {login.isPending ? 'Signing in…' : 'Sign in'}
        </Button>
      </div>

      <p className="text-center text-sm text-muted-foreground">Need access? Ask your admin to add your email.</p>
    </form>
  )
}

const INPUT =
  'h-11 w-full rounded-lg border bg-surface pr-3 pl-10 text-[15px] outline-none transition-colors placeholder:text-muted-foreground/80 hover:border-foreground/25 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/40'

function Field({ id, label, icon, action, children }: { id: string; label: string; icon: ReactNode; action?: ReactNode; children: ReactNode }) {
  return (
    <div className="space-y-2">
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      <div className="relative">
        <span className="pointer-events-none absolute top-1/2 left-3.5 -translate-y-1/2 text-muted-foreground">{icon}</span>
        {children}
        {action && <span className="absolute top-1/2 right-1.5 -translate-y-1/2">{action}</span>}
      </div>
    </div>
  )
}
