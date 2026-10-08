import { ArrowLeft } from 'lucide-react'
import { Link, useParams } from 'react-router'
import { CallView } from '@/components/calls/CallView'

// PRD §6.5: Call Detail — the same call screen as the Lead Details Conversations tab, full-width.
export default function CallDetailPage() {
  const params = useParams()
  return (
    <>
      <Link
        to="/calls"
        className="mb-4 inline-flex items-center gap-1.5 rounded-sm text-muted-foreground hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
      >
        <ArrowLeft className="size-4" aria-hidden />
        All calls
      </Link>
      <CallView callId={Number(params.callId)} />
    </>
  )
}
