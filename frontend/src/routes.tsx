// Every URL in the app (PRD §5). `handle.title` is shown in the top bar.

import { createBrowserRouter, Navigate } from 'react-router'
import { AppShell } from '@/components/layout/AppShell'
import { RouteError } from '@/components/layout/RouteError'
import BatchDetailPage from '@/pages/BatchDetailPage'
import BatchesPage from '@/pages/BatchesPage'
import CallDetailPage from '@/pages/CallDetailPage'
import CallsPage from '@/pages/CallsPage'
import ComparePage from '@/pages/ComparePage'
import LeadDetailPage from '@/pages/LeadDetailPage'
import LeadsPage from '@/pages/LeadsPage'
import NotFoundPage from '@/pages/NotFoundPage'
import SettingsPage from '@/pages/SettingsPage'
import UploadPage from '@/pages/UploadPage'

export const router = createBrowserRouter([
  {
    element: <AppShell />,
    errorElement: <RouteError />,
    children: [
      { index: true, element: <Navigate to="/upload" replace /> },
      { path: 'upload', element: <UploadPage />, handle: { title: 'Upload' } },
      { path: 'batches', element: <BatchesPage />, handle: { title: 'Batches' } },
      { path: 'batches/:batchId', element: <BatchDetailPage />, handle: { title: 'Batch progress' } },
      { path: 'leads', element: <LeadsPage />, handle: { title: 'All Conversations' } },
      { path: 'leads/:leadId', element: <LeadDetailPage />, handle: { title: 'Lead Details' } },
      { path: 'calls', element: <CallsPage />, handle: { title: 'Calls' } },
      { path: 'calls/:callId', element: <CallDetailPage />, handle: { title: 'Call' } },
      { path: 'compare', element: <ComparePage />, handle: { title: 'AI vs Human' } },
      { path: 'settings', element: <SettingsPage />, handle: { title: 'Settings' } },
      { path: '*', element: <NotFoundPage />, handle: { title: 'Not found' } },
    ],
  },
])
