import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { leadsApi } from '@/lib/api-leads'
import type { LeadAction } from '@/lib/types-leads'
import { cn } from '@/lib/utils'

/** Tasks for this lead: AI-suggested and manual. Tick to mark done, change the due date, add or delete. */
export function ActionsTab({ leadId, actions }: { leadId: number; actions: LeadAction[] }) {
  const qc = useQueryClient()
  const [title, setTitle] = useState('')
  const [due, setDue] = useState('')
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['lead', leadId] })
    qc.invalidateQueries({ queryKey: ['leads'] }) // "Next Task Due Date" column
  }
  const update = useMutation({
    mutationFn: ({ id, ...body }: { id: number; done?: boolean; due_date?: string | null }) =>
      leadsApi.updateAction(id, body),
    onSuccess: refresh,
  })
  const remove = useMutation({ mutationFn: leadsApi.deleteAction, onSuccess: refresh })
  const add = useMutation({
    mutationFn: (body: { title: string; due_date: string | null }) => leadsApi.addAction(leadId, body),
    onSuccess: () => {
      setTitle('')
      setDue('')
      refresh()
    },
  })

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (title.trim()) add.mutate({ title: title.trim(), due_date: due || null })
  }

  const open = actions.filter((a) => !a.done)
  const done = actions.filter((a) => a.done)
  const error = update.error ?? remove.error ?? add.error

  return (
    <div className="space-y-4">
      <form onSubmit={submit} className="flex flex-wrap items-end gap-2 rounded-xl border bg-surface p-4">
        <label className="grid min-w-0 flex-1 basis-60 gap-1">
          <span className="text-xs text-muted-foreground">New task</span>
          <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Customer visit to shop" />
        </label>
        <label className="grid gap-1">
          <span className="text-xs text-muted-foreground">Due date</span>
          <Input type="date" value={due} onChange={(e) => setDue(e.target.value)} className="num w-40" />
        </label>
        <Button type="submit" disabled={!title.trim() || add.isPending}>
          <Plus />
          Add task
        </Button>
      </form>

      {error && (
        <p role="alert" className="rounded-lg bg-negative-soft px-3 py-2 text-negative">
          {error.message}
        </p>
      )}

      <TaskList
        title="Open"
        items={open}
        empty="No open tasks."
        onToggle={(a, on) => update.mutate({ id: a.id, done: on })}
        onDue={(a, d) => update.mutate({ id: a.id, due_date: d || null })}
        onDelete={(a) => remove.mutate(a.id)}
      />
      {done.length > 0 && (
        <TaskList
          title="Done"
          items={done}
          empty=""
          onToggle={(a, on) => update.mutate({ id: a.id, done: on })}
          onDue={(a, d) => update.mutate({ id: a.id, due_date: d || null })}
          onDelete={(a) => remove.mutate(a.id)}
        />
      )}
    </div>
  )
}

interface TaskListProps {
  title: string
  items: LeadAction[]
  empty: string
  onToggle: (a: LeadAction, done: boolean) => void
  onDue: (a: LeadAction, date: string) => void
  onDelete: (a: LeadAction) => void
}

function TaskList({ title, items, empty, onToggle, onDue, onDelete }: TaskListProps) {
  return (
    <section className="rounded-xl border bg-surface">
      <h3 className="border-b px-4 py-3 font-semibold">
        {title} <span className="num font-normal text-muted-foreground">({items.length})</span>
      </h3>
      {items.length === 0 ? (
        <p className="px-4 py-3 text-muted-foreground">{empty}</p>
      ) : (
        <ul className="divide-y">
          {items.map((a) => (
            <li key={a.id} className="flex flex-wrap items-start gap-3 px-4 py-3">
              <Checkbox
                className="mt-1"
                checked={a.done}
                aria-label={a.done ? `Mark "${a.title}" as open` : `Mark "${a.title}" as done`}
                onCheckedChange={(c) => onToggle(a, c === true)}
              />
              <div className="min-w-0 flex-1 basis-56 space-y-1">
                <p className={cn('font-medium', a.done && 'text-muted-foreground line-through')}>
                  {a.title}
                  {a.source === 'ai' && (
                    <span className="ml-2 rounded-full bg-ai-soft px-1.5 py-0.5 text-[11px] font-normal text-ai">
                      AI suggested
                    </span>
                  )}
                </p>
                {a.say && (
                  <p>
                    <span aria-hidden>👉 </span>
                    <span className="font-semibold">Say:</span> {a.say}
                  </p>
                )}
                {a.why && <p className="text-muted-foreground">{a.why}</p>}
              </div>
              <label className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">Due</span>
                <Input
                  type="date"
                  value={a.due_date ?? ''}
                  onChange={(e) => onDue(a, e.target.value)}
                  className="num w-40"
                />
              </label>
              <Button variant="ghost" size="icon-sm" aria-label={`Delete "${a.title}"`} onClick={() => onDelete(a)}>
                <Trash2 />
              </Button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
