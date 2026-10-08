import { TriangleAlert } from 'lucide-react'
import { isRouteErrorResponse, useRouteError } from 'react-router'
import { EmptyState } from '@/components/EmptyState'

/** Last-resort screen if a page crashes while rendering. */
export function RouteError() {
  const error = useRouteError()
  const message = isRouteErrorResponse(error)
    ? `${error.status} ${error.statusText}`
    : error instanceof Error
      ? error.message
      : 'Unknown error'
  return (
    <div className="mx-auto max-w-xl p-8">
      <EmptyState
        icon={TriangleAlert}
        title="This page hit a problem"
        description={message}
        action={
          <a className="underline" href="/upload">
            Back to Upload
          </a>
        }
      />
    </div>
  )
}
