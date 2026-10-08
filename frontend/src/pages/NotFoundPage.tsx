import { Compass } from 'lucide-react'
import { Link } from 'react-router'
import { EmptyState } from '@/components/EmptyState'
import { Button } from '@/components/ui/button'

export default function NotFoundPage() {
  return (
    <EmptyState
      icon={Compass}
      title="Page not found"
      description="This page doesn't exist. Check the link, or start from the uploader."
      action={
        <Button asChild>
          <Link to="/upload">Go to Upload</Link>
        </Button>
      }
    />
  )
}
