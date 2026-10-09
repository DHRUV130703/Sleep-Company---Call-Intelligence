import { useMutation } from '@tanstack/react-query'
import { RefreshCw, Sparkles } from 'lucide-react'
import { Link } from 'react-router'
import { Button } from '@/components/ui/button'
import { compareApi } from '@/lib/api-compare'
import type { CompareResult, CompareScope } from '@/lib/types-compare'

/** Shown when some bot calls were reviewed with an older prompt: one click re-analyses just those calls. */
export function OutdatedReviewsNotice({ data, scope }: { data: CompareResult; scope: CompareScope }) {
  const update = useMutation({ mutationFn: () => compareApi.updateBotReviews(scope) })
  const n = data.outdated_bot_reviews
  if (!n && !update.isSuccess) return null

  return (
    <div role="status" aria-live="polite" className="flex flex-wrap items-start gap-3 rounded-xl border bg-ai-soft px-4 py-3">
      <Sparkles className="mt-0.5 size-4 shrink-0 text-ai" aria-hidden />
      {update.isSuccess ? (
        <p className="min-w-0 flex-1">
          {update.data.queued} bot {update.data.queued === 1 ? 'call is' : 'calls are'} being re-analysed. Follow progress
          on the <Link to="/batches" className="underline underline-offset-4">Batches</Link> page, then press “Re-run
          comparison”.
        </p>
      ) : (
        <>
          <p className="min-w-0 flex-1">
            {n} bot {n === 1 ? 'call was' : 'calls were'} reviewed before “Better” lines existed. Update them to see what the
            bot should have said at each weak moment.
            {update.isError && <span className="block text-negative">{update.error.message}</span>}
          </p>
          <Button size="sm" onClick={() => update.mutate()} disabled={update.isPending}>
            <RefreshCw className={update.isPending ? 'size-4 animate-spin motion-reduce:animate-none' : 'size-4'} aria-hidden />
            Update bot reviews
          </Button>
        </>
      )}
    </div>
  )
}
