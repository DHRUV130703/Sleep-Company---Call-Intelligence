import type { ReactNode } from 'react'
import { Card, CardContent, CardDescription, CardHeader } from '@/components/ui/card'
import { cn } from '@/lib/utils'

interface Props {
  /** Anchor id, used by the mini table of contents. */
  id: string
  title: string
  caption: ReactNode
  /** Optional control on the right of the title (e.g. "Show as a table"). */
  action?: ReactNode
  className?: string
  children: ReactNode
}

/** One section card of the AI vs Human report: title, one-line caption, content. */
export function CompareSection({ id, title, caption, action, className, children }: Props) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="scroll-mt-20">
      <Card className={cn('gap-5 py-5', className)}>
        <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3 px-5">
          <div className="min-w-0">
            <h3 id={`${id}-title`} className="text-base font-semibold">
              {title}
            </h3>
            <CardDescription className="mt-0.5">{caption}</CardDescription>
          </div>
          {action}
        </CardHeader>
        <CardContent className="px-5">{children}</CardContent>
      </Card>
    </section>
  )
}

/** Column heading for one side. AI is always first (left), Human second (right). */
export function SideLabel({ side, className }: { side: 'ai' | 'human'; className?: string }) {
  return (
    <span className={cn('inline-flex items-center gap-1.5 font-medium', className)}>
      <span className={cn('size-2 rounded-full', side === 'ai' ? 'bg-ai' : 'bg-human')} aria-hidden />
      {side === 'ai' ? 'AI voice bot' : 'Human agents'}
    </span>
  )
}
