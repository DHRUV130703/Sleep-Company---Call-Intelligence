import type { ReactNode } from 'react'

interface Props {
  title: string
  description?: ReactNode
  actions?: ReactNode
}

/** Big page title + one-line description, with optional actions on the right. */
export function PageHeader({ title, description, actions }: Props) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h2 className="text-2xl font-semibold tracking-tight">{title}</h2>
        {description && <p className="mt-1 max-w-2xl text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  )
}
