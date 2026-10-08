import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

interface Props {
  icon: LucideIcon
  title: string
  description: ReactNode
  action?: ReactNode
  children?: ReactNode
}

/** Shown when a list or page has nothing yet. One clear message, one call to action. */
export function EmptyState({ icon: Icon, title, description, action, children }: Props) {
  return (
    <div className="flex flex-col items-center rounded-xl border border-dashed bg-surface px-6 py-16 text-center">
      <div className="mb-4 grid size-12 place-items-center rounded-full bg-surface-sunken text-muted-foreground">
        <Icon className="size-6" aria-hidden />
      </div>
      <h3 className="text-base font-semibold">{title}</h3>
      <p className="mt-1 max-w-md text-muted-foreground">{description}</p>
      {children}
      {action && <div className="mt-6">{action}</div>}
    </div>
  )
}
