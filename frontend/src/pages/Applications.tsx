import { useMemo } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { DeadlineBadge, SourceBadge } from '../components/Badges'
import { EmptyState, ErrorNote, Spinner } from '../components/Spinner'
import { request } from '../lib/api'
import { formatDate, statusLabel } from '../lib/format'
import type { AppStatus, Application } from '../types'

const COLUMNS: { status: AppStatus; hint: string }[] = [
  { status: 'saved', hint: 'Shortlisted, not started' },
  { status: 'applied', hint: 'Form submitted' },
  { status: 'under_review', hint: 'Waiting on the provider' },
  { status: 'awarded', hint: 'Congratulations' },
  { status: 'rejected', hint: 'Closed out' },
]

const ALL_STATUSES: AppStatus[] = [
  'saved',
  'applied',
  'under_review',
  'awarded',
  'rejected',
]

const COLUMN_ACCENT: Record<AppStatus, string> = {
  saved: 'border-t-slate-300',
  applied: 'border-t-accent-500',
  under_review: 'border-t-amber-400',
  awarded: 'border-t-emerald-500',
  rejected: 'border-t-red-400',
}

export function Applications() {
  const queryClient = useQueryClient()

  const applications = useQuery({
    queryKey: ['applications'],
    queryFn: () => request<Application[]>('/applications'),
  })

  function invalidate() {
    void queryClient.invalidateQueries({ queryKey: ['applications'] })
    void queryClient.invalidateQueries({ queryKey: ['scholarships'] })
  }

  const update = useMutation({
    mutationFn: (vars: { id: number; status: AppStatus }) =>
      request<Application>(`/applications/${vars.id}`, {
        method: 'PATCH',
        body: { status: vars.status },
      }),
    onSuccess: invalidate,
  })

  const remove = useMutation({
    mutationFn: (id: number) =>
      request<void>(`/applications/${id}`, { method: 'DELETE' }),
    onSuccess: invalidate,
  })

  const grouped = useMemo(() => {
    const buckets: Record<AppStatus, Application[]> = {
      saved: [],
      applied: [],
      under_review: [],
      awarded: [],
      rejected: [],
    }
    for (const application of applications.data ?? []) {
      buckets[application.status]?.push(application)
    }
    // Soonest deadline first within each column, undated last.
    for (const status of ALL_STATUSES) {
      buckets[status].sort((a, b) => {
        const left = a.scholarship?.deadline ?? ''
        const right = b.scholarship?.deadline ?? ''
        if (!left && !right) return 0
        if (!left) return 1
        if (!right) return -1
        return left.localeCompare(right)
      })
    }
    return buckets
  }, [applications.data])

  if (applications.isLoading) return <Spinner label="Loading your tracker" />
  if (applications.isError) return <ErrorNote error={applications.error} />

  const total = applications.data?.length ?? 0

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-slate-900">
          My applications
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          {total === 0
            ? 'Nothing tracked yet.'
            : `${total} scholarship${total === 1 ? '' : 's'} tracked. Move each one along as you go.`}
        </p>
      </div>

      {update.isError ? <ErrorNote error={update.error} /> : null}
      {remove.isError ? <ErrorNote error={remove.error} /> : null}

      {total === 0 ? (
        <EmptyState
          title="Your tracker is empty"
          hint="Save a scholarship from the dashboard, or hit Apply — it gets added automatically."
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
          {COLUMNS.map((column) => {
            const entries = grouped[column.status]
            return (
              <section
                key={column.status}
                className={`rounded-lg border border-slate-200 border-t-2 bg-slate-100/60 ${COLUMN_ACCENT[column.status]}`}
              >
                <header className="px-3 py-3">
                  <div className="flex items-baseline justify-between gap-2">
                    <h2 className="text-sm font-semibold text-slate-800">
                      {statusLabel(column.status)}
                    </h2>
                    <span className="text-xs font-medium tabular-nums text-slate-500">
                      {entries.length}
                    </span>
                  </div>
                  <p className="mt-0.5 text-xs text-slate-500">{column.hint}</p>
                </header>

                <div className="space-y-2 px-2 pb-2">
                  {entries.length === 0 ? (
                    <p className="px-1 py-3 text-xs text-slate-400">Nothing here.</p>
                  ) : (
                    entries.map((application) => {
                      const scholarship = application.scholarship
                      return (
                        <article
                          key={application.id}
                          className="card space-y-2.5 p-3"
                        >
                          <h3 className="text-sm font-medium leading-snug text-slate-900">
                            {scholarship?.title ?? 'Scholarship'}
                          </h3>

                          {scholarship?.provider ? (
                            <p className="truncate text-xs text-slate-500">
                              {scholarship.provider}
                            </p>
                          ) : null}

                          <div className="flex flex-wrap items-center gap-1.5">
                            {scholarship ? (
                              <SourceBadge source={scholarship.source} />
                            ) : null}
                            <DeadlineBadge daysLeft={scholarship?.days_left ?? null} />
                          </div>

                          {application.applied_on ? (
                            <p className="text-xs text-slate-500">
                              Applied {formatDate(application.applied_on)}
                            </p>
                          ) : null}

                          <div>
                            <label
                              className="sr-only"
                              htmlFor={`status-${application.id}`}
                            >
                              Status for {scholarship?.title ?? 'this scholarship'}
                            </label>
                            <select
                              id={`status-${application.id}`}
                              value={application.status}
                              disabled={update.isPending}
                              onChange={(event) =>
                                update.mutate({
                                  id: application.id,
                                  status: event.target.value as AppStatus,
                                })
                              }
                              className="input py-1.5 text-xs"
                            >
                              {ALL_STATUSES.map((status) => (
                                <option key={status} value={status}>
                                  {statusLabel(status)}
                                </option>
                              ))}
                            </select>
                          </div>

                          <div className="flex items-center justify-between gap-2 pt-0.5">
                            {scholarship ? (
                              <a
                                href={scholarship.apply_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-xs font-medium text-accent-700 hover:underline"
                              >
                                Open ↗
                              </a>
                            ) : (
                              <span />
                            )}
                            <button
                              type="button"
                              onClick={() => remove.mutate(application.id)}
                              disabled={remove.isPending}
                              className="text-xs text-slate-400 hover:text-red-600"
                            >
                              Remove
                            </button>
                          </div>
                        </article>
                      )
                    })
                  )}
                </div>
              </section>
            )
          })}
        </div>
      )}
    </div>
  )
}
