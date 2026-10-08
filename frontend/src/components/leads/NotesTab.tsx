import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { leadsApi } from '@/lib/api-leads'
import { formatDateTime } from '@/lib/format'
import type { LeadNote } from '@/lib/types-leads'

/** Free-text notes about the lead, newest first. Stored in the local database. */
export function NotesTab({ leadId, notes }: { leadId: number; notes: LeadNote[] }) {
  const qc = useQueryClient()
  const [body, setBody] = useState('')
  const refresh = () => qc.invalidateQueries({ queryKey: ['lead', leadId] })
  const add = useMutation({
    mutationFn: (text: string) => leadsApi.addNote(leadId, text),
    onSuccess: () => {
      setBody('')
      refresh()
    },
  })
  const remove = useMutation({ mutationFn: leadsApi.deleteNote, onSuccess: refresh })

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (body.trim()) add.mutate(body.trim())
  }
  const error = add.error ?? remove.error

  return (
    <div className="space-y-4">
      <form onSubmit={submit} className="space-y-2 rounded-xl border bg-surface p-4">
        <label htmlFor="new-note" className="text-xs text-muted-foreground">
          Add a note
        </label>
        <Textarea
          id="new-note"
          rows={3}
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="e.g. Prefers a call after 7 pm. Comparing with Wakefit."
        />
        <div className="flex justify-end">
          <Button type="submit" disabled={!body.trim() || add.isPending}>
            Add note
          </Button>
        </div>
      </form>

      {error && (
        <p role="alert" className="rounded-lg bg-negative-soft px-3 py-2 text-negative">
          {error.message}
        </p>
      )}

      {notes.length === 0 ? (
        <p className="text-muted-foreground">No notes yet.</p>
      ) : (
        <ul className="space-y-3">
          {notes.map((n) => (
            <li key={n.id} className="flex items-start gap-3 rounded-xl border bg-surface p-4">
              <div className="min-w-0 flex-1">
                <p className="font-mono text-xs text-muted-foreground">{formatDateTime(n.created_at)}</p>
                <p className="mt-1 break-words whitespace-pre-wrap">{n.body}</p>
              </div>
              <Button variant="ghost" size="icon-sm" aria-label="Delete note" onClick={() => remove.mutate(n.id)}>
                <Trash2 />
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
