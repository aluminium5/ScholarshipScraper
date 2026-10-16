import { useEffect, useRef } from 'react'

import { DeadlineBadge, SourceBadge, StatusPill } from './Badges'
import { formatDate, levelLabel, sourceLabel, tagLabel } from '../lib/format'
import type { Scholarship } from '../types'

interface Props {
  scholarship: Scholarship | null
  onClose: () => void
  onApply: (scholarship: Scholarship) => void
  onSave: (scholarship: Scholarship) => void
}

/**
 * Portals that have no public per-scheme page need a note telling the student
 * exactly what to select after logging in (spec §6).
 */
function loginNote(scholarship: Scholarship): string | null {
  if (scholarship.source === 'nsp') {
    return `NSP requires One Time Registration (OTR). After logging in, select: ${scholarship.title}`
  }
  if (scholarship.source === 'vidyasaarathi') {
    return `Vidyasaarathi requires a login. Open the Open Schemes tab and select: ${scholarship.title}`
  }
  return null
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="label">{label}</dt>
      <dd className="text-sm text-slate-800">{children}</dd>
    </div>
  )
}

export function ScholarshipDrawer({ scholarship, onClose, onApply, onSave }: Props) {
  const closeRef = useRef<HTMLButtonElement>(null)
  const open = scholarship !== null

  // Escape to close, and don't let the page behind scroll.
  useEffect(() => {
    if (!open) return
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    closeRef.current?.focus()
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = previous
    }
  }, [open, onClose])

  if (!scholarship) return null

  const note = loginNote(scholarship)

  return (
    <div className="fixed inset-0 z-40 flex justify-end" role="dialog" aria-modal="true">
      <button
        type="button"
        aria-label="Close details"
        onClick={onClose}
        className="absolute inset-0 cursor-default bg-slate-900/20"
      />

      <aside className="relative flex h-full w-full max-w-lg flex-col overflow-y-auto border-l border-slate-200 bg-white shadow-xl">
        <header className="sticky top-0 flex items-start justify-between gap-4 border-b border-slate-200 bg-white px-5 py-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <SourceBadge source={scholarship.source} />
              {scholarship.application_status ? (
                <StatusPill status={scholarship.application_status} />
              ) : null}
            </div>
            <h2 className="mt-2 text-lg font-semibold leading-snug text-slate-900">
              {scholarship.title}
            </h2>
            {scholarship.provider ? (
              <p className="mt-1 text-sm text-slate-600">{scholarship.provider}</p>
            ) : null}
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            className="btn-ghost shrink-0 px-2"
            aria-label="Close"
          >
            <svg viewBox="0 0 20 20" fill="currentColor" className="h-5 w-5" aria-hidden="true">
              <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
            </svg>
          </button>
        </header>

        <div className="flex-1 space-y-6 px-5 py-5">
          <div className="flex flex-wrap items-center gap-3">
            <DeadlineBadge daysLeft={scholarship.days_left} />
            {scholarship.award_amount ? (
              <span className="text-sm font-medium text-slate-800">
                {scholarship.award_amount}
              </span>
            ) : null}
          </div>

          {note ? (
            <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-amber-800">
                Before you apply
              </p>
              <p className="mt-1 text-sm text-amber-900">{note}</p>
            </div>
          ) : null}

          <dl className="grid grid-cols-2 gap-4">
            <Field label="Opens">{formatDate(scholarship.opens_at)}</Field>
            <Field label="Closes">{formatDate(scholarship.deadline)}</Field>
            <Field label="Study level">{levelLabel(scholarship.level)}</Field>
            <Field label="Source">{sourceLabel(scholarship.source)}</Field>
          </dl>

          {scholarship.description ? (
            <div>
              <h3 className="label">About</h3>
              <p className="whitespace-pre-line text-sm leading-relaxed text-slate-700">
                {scholarship.description}
              </p>
            </div>
          ) : null}

          {scholarship.eligibility ? (
            <div>
              <h3 className="label">Eligibility</h3>
              <p className="whitespace-pre-line text-sm leading-relaxed text-slate-700">
                {scholarship.eligibility}
              </p>
            </div>
          ) : null}

          {scholarship.tags.length ? (
            <div>
              <h3 className="label">Tags</h3>
              <ul className="flex flex-wrap gap-1.5">
                {scholarship.tags.map((tag) => (
                  <li
                    key={tag}
                    className="rounded border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs text-slate-600"
                  >
                    {tagLabel(tag)}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {scholarship.info_url ? (
            <a
              href={scholarship.info_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-sm font-medium text-accent-700 hover:text-accent-800 hover:underline"
            >
              Guidelines and details
              <span aria-hidden="true">↗</span>
            </a>
          ) : null}
        </div>

        <footer className="sticky bottom-0 flex items-center gap-2 border-t border-slate-200 bg-white px-5 py-4">
          <button
            type="button"
            onClick={() => onSave(scholarship)}
            className="btn-secondary flex-1"
          >
            {scholarship.application_status ? 'Tracked' : 'Save to tracker'}
          </button>
          <button
            type="button"
            onClick={() => onApply(scholarship)}
            className="btn-primary flex-1"
          >
            Apply
            <span aria-hidden="true">↗</span>
          </button>
        </footer>
      </aside>
    </div>
  )
}
