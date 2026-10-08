import { Bot, UserRound } from 'lucide-react'
import { cn } from '@/lib/utils'

/** "AI" (blue) or "Human" (orange) label. Used everywhere a call or lead side is shown. */
export function AgentChip({ type, className }: { type: 'ai' | 'human'; className?: string }) {
  const isAi = type === 'ai'
  const Icon = isAi ? Bot : UserRound
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
        isAi ? 'bg-ai-soft text-ai' : 'bg-human-soft text-human',
        className,
      )}
    >
      <Icon className="size-3.5" aria-hidden />
      {isAi ? 'AI voice bot' : 'Human agents'}
    </span>
  )
}
