import { request } from '@/lib/api'
import type { Batch, BatchCreate, BatchDetail, SheetCheck, SheetPreview } from '@/lib/types-batches'

export const batchesApi = {
  list: () => request<{ items: Batch[] }>('/batches'),
  get: (id: number) => request<BatchDetail>(`/batches/${id}`),
  create: (body: BatchCreate) => request<Batch>('/batches', { method: 'POST', body: JSON.stringify(body) }),
  retryFailed: (id: number) => request<{ retried: number }>(`/batches/${id}/retry-failed`, { method: 'POST' }),
  cancel: (id: number) => request<{ cancelled: number }>(`/batches/${id}/cancel`, { method: 'POST' }),
  retryCall: (callId: number) => request<{ ok: boolean }>(`/calls/${callId}/retry`, { method: 'POST' }),

  previewSheet: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<SheetPreview>('/sheets/preview', { method: 'POST', body: form })
  },
  checkSheet: (sheetId: string, mapping: Record<string, string | null>, agentTypeMode: string) =>
    request<SheetCheck>(`/sheets/${sheetId}/check`, {
      method: 'POST',
      body: JSON.stringify({ mapping, agent_type_mode: agentTypeMode }),
    }),
}
