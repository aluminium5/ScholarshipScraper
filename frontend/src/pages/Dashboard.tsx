import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { ErrorNote, EmptyState, Spinner } from '../components/Spinner'
import { ScholarshipCard } from '../components/ScholarshipCard'
import { ScholarshipDrawer } from '../components/ScholarshipDrawer'
import { useAuth } from '../context/AuthContext'
import { query, request } from '../lib/api'
import { levelLabel, relativeTime, sourceLabel, tagLabel } from '../lib/format'
import type {
  Application,
  RefreshResult,
  Scholarship,
  ScholarshipList,
  ScholarshipMeta,
} from '../types'

const LEVELS = ['school', 'ug', 'pg', 'phd'] as const
const TAGS = ['girls', 'merit', 'need', 'sc_st', 'obc', 'pwd', 'minority'] as const
const DUE_WINDOWS = [
  { days: 7, label: 'Closing in 7 days' },
  { days: 30, label: 'Closing in 30 days' },
] as const

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="card px-4 py-3">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums text-slate-900">{value}</p>
      {hint ? <p className="mt-0.5 text-xs text-slate-500">{hint}</p> : null}
    </div>
  )
}

export function Dashboard() {
  const queryClient = useQueryClient()
  const { user } = useAuth()

  const [search, setSearch] = useState('')
  const [source, setSource] = useState<string | undefined>()
  const [level, setLevel] = useState<string | undefined>()
  const [tags, setTags] = useState<string[]>([])
  const [dueWithin, setDueWithin] = useState<number | undefined>()
  const [includeExpired, setIncludeExpired] = useState(false)
  const [selected, setSelected] = useState<Scholarship | null>(null)

  const listKey = ['scholarships', { search, source, level, tags, dueWithin, includeExpired }]

  const list = useQuery({
    queryKey: listKey,
    queryFn: () =>
      request<ScholarshipList>(
        `/scholarships${query({
          q: search.trim() || undefined,
          source,
          level,
          tag: tags,
          due_within_days: dueWithin,
          include_expired: includeExpired,
        })}`,
      ),
  })

  const meta = useQuery({
    queryKey: ['scholarships', 'meta'],
    queryFn: () => request<ScholarshipMeta>('/scholarships/meta'),
  })

  const applications = useQuery({
    queryKey: ['applications'],
    queryFn: () => request<Application[]>('/applications'),
  })

  /** Upsert a tracker entry. Used by both Save and Apply. */
  const track = useMutation({
    mutationFn: (vars: { id: number; status: 'saved' | 'applied' }) =>
      request<Application>('/applications', {
        method: 'POST',
        body: { scholarship_id: vars.id, status: vars.status },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['scholarships'] })
      void queryClient.invalidateQueries({ queryKey: ['applications'] })
    },
  })

  const refresh = useMutation({
    mutationFn: () => request<RefreshResult>('/admin/refresh', { method: 'POST' }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['scholarships'] })
    },
  })

  /**
   * Apply opens the scholarship's own page and records it as saved (spec §6).
   * The window is opened synchronously so the browser does not treat it as a
   * popup, and the tracker call happens alongside it.
   */
  function onApply(scholarship: Scholarship) {
    window.open(scholarship.apply_url, '_blank', 'noopener,noreferrer')
    if (!scholarship.application_status) {
      track.mutate({ id: scholarship.id, status: 'saved' })
    }
  }

  function onSave(scholarship: Scholarship) {
    if (scholarship.application_status) return
    track.mutate({ id: scholarship.id, status: 'saved' })
  }

  function toggleTag(tag: string) {
    setTags((current) =>
      current.includes(tag) ? current.filter((t) => t !== tag) : [...current, tag],
    )
  }

  function clearFilters() {
    setSearch('')
    setSource(undefined)
    setLevel(undefined)
    setTags([])
    setDueWithin(undefined)
    setIncludeExpired(false)
  }

  const appliedCount = useMemo(
    () =>
      (applications.data ?? []).filter((a) => a.status !== 'saved').length,
    [applications.data],
  )

  const filtersActive =
    Boolean(search.trim() || source || level || dueWithin || includeExpired) || tags.length > 0

  const availableSources = meta.data?.sources ?? []
  const items = list.data?.items ?? []

  // Keep the drawer in step with refreshed list data.
  const selectedLive =
    selected === null ? null : (items.find((i) => i.id === selected.id) ?? selected)

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-slate-900">
            Open scholarships
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            Nearest deadline first. Expired scholarships are hidden.
          </p>
        </div>
        {user?.is_admin ? (
          <button
            type="button"
            onClick={() => refresh.mutate()}
            disabled={refresh.isPending}
            className="btn-secondary"
          >
            {refresh.isPending ? 'Refreshing…' : 'Refresh now'}
          </button>
        ) : null}
      </div>

      {refresh.isError ? <ErrorNote error={refresh.error} /> : null}

      {/* Summary strip */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat
          label="Closing this week"
          value={meta.data ? String(meta.data.closing_this_week) : '—'}
        />
        <Stat label="Open now" value={meta.data ? String(meta.data.total_active) : '—'} />
        <Stat label="Applied" value={applications.data ? String(appliedCount) : '—'} />
        <Stat
          label="Last updated"
          value={meta.data ? relativeTime(meta.data.last_refresh_at) : '—'}
          hint={meta.data?.last_refresh_at ? undefined : 'No refresh recorded yet'}
        />
      </div>

      {/* Search + filters */}
      <div className="card space-y-4 p-4">
        <div className="flex flex-col gap-3 sm:flex-row">
          <div className="flex-1">
            <label htmlFor="search" className="sr-only">
              Search scholarships
            </label>
            <input
              id="search"
              type="search"
              className="input"
              placeholder="Search by name, provider or eligibility…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          {filtersActive ? (
            <button type="button" onClick={clearFilters} className="btn-secondary">
              Clear filters
            </button>
          ) : null}
        </div>

        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="w-16 text-xs font-medium uppercase tracking-wide text-slate-500">
              Source
            </span>
            <button
              type="button"
              onClick={() => setSource(undefined)}
              className={source === undefined ? 'chip-on' : 'chip-off'}
            >
              All
            </button>
            {availableSources.map((entry) => (
              <button
                key={entry.source}
                type="button"
                onClick={() =>
                  setSource((current) => (current === entry.source ? undefined : entry.source))
                }
                className={source === entry.source ? 'chip-on' : 'chip-off'}
              >
                {sourceLabel(entry.source)}
                <span className="opacity-60">{entry.count}</span>
              </button>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="w-16 text-xs font-medium uppercase tracking-wide text-slate-500">
              Level
            </span>
            <button
              type="button"
              onClick={() => setLevel(undefined)}
              className={level === undefined ? 'chip-on' : 'chip-off'}
            >
              Any
            </button>
            {LEVELS.map((value) => (
              <button
                key={value}
                type="button"
                onClick={() =>
                  setLevel((current) => (current === value ? undefined : value))
                }
                className={level === value ? 'chip-on' : 'chip-off'}
              >
                {levelLabel(value)}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="w-16 text-xs font-medium uppercase tracking-wide text-slate-500">
              Tags
            </span>
            {TAGS.map((tag) => (
              <button
                key={tag}
                type="button"
                onClick={() => toggleTag(tag)}
                className={tags.includes(tag) ? 'chip-on' : 'chip-off'}
              >
                {tagLabel(tag)}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="w-16 text-xs font-medium uppercase tracking-wide text-slate-500">
              Urgency
            </span>
            {DUE_WINDOWS.map((window) => (
              <button
                key={window.days}
                type="button"
                onClick={() =>
                  setDueWithin((current) => (current === window.days ? undefined : window.days))
                }
                className={dueWithin === window.days ? 'chip-on' : 'chip-off'}
              >
                {window.label}
              </button>
            ))}
            <button
              type="button"
              onClick={() => setIncludeExpired((value) => !value)}
              className={includeExpired ? 'chip-on' : 'chip-off'}
            >
              Include expired
            </button>
          </div>
        </div>
      </div>

      {/* Results */}
      {list.isLoading ? (
        <Spinner label="Finding scholarships" />
      ) : list.isError ? (
        <ErrorNote error={list.error} />
      ) : items.length === 0 ? (
        <EmptyState
          title="No scholarships match these filters"
          hint={
            filtersActive
              ? 'Try clearing a filter or widening the deadline window.'
              : 'Once a refresh has run, open scholarships will appear here.'
          }
        />
      ) : (
        <>
          <p className="text-sm text-slate-600">
            {list.data?.total === 1 ? '1 scholarship' : `${list.data?.total} scholarships`}
          </p>
          <div className="space-y-3">
            {items.map((scholarship) => (
              <ScholarshipCard
                key={scholarship.id}
                scholarship={scholarship}
                onOpen={setSelected}
                onApply={onApply}
                onSave={onSave}
                busy={track.isPending}
              />
            ))}
          </div>
        </>
      )}

      <ScholarshipDrawer
        scholarship={selectedLive}
        onClose={() => setSelected(null)}
        onApply={onApply}
        onSave={onSave}
      />
    </div>
  )
}
