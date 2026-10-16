import { DeadlineBadge, SourceBadge, StatusPill } from './Badges'
import { formatDate, levelLabel, tagLabel } from '../lib/format'
import type { Scholarship } from '../types'

interface Props {
  scholarship: Scholarship
  onOpen: (scholarship: Scholarship) => void
  onApply: (scholarship: Scholarship) => void
  onSave: (scholarship: Scholarship) => void
  busy?: boolean
}

export function ScholarshipCard({ scholarship, onOpen, onApply, onSave, busy }: Props) {
  const { title, provider, award_amount, tags, deadline, days_left } = scholarship

  return (
    <article className="card p-4 transition-colors hover:border-slate-300 sm:p-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 flex-1">
          {/* The whole heading is the drawer trigger, so it stays keyboard reachable. */}
          <button
            type="button"
            onClick={() => onOpen(scholarship)}
            className="group block w-full text-left"
          >
            <h3 className="text-base font-semibold text-slate-900 group-hover:text-accent-700">
              {title}
            </h3>
          </button>

          {provider ? (
            <p className="mt-1 truncate text-sm text-slate-600">{provider}</p>
          ) : null}

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <SourceBadge source={scholarship.source} />
            <span className="text-xs text-slate-500">{levelLabel(scholarship.level)}</span>
            {award_amount ? (
              <>
                <span aria-hidden="true" className="text-slate-300">
                  ·
                </span>
                <span className="text-xs font-medium text-slate-700">{award_amount}</span>
              </>
            ) : null}
            {scholarship.application_status ? (
              <StatusPill status={scholarship.application_status} />
            ) : null}
          </div>

          {tags.length ? (
            <ul className="mt-3 flex flex-wrap gap-1.5">
              {tags.slice(0, 5).map((tag) => (
                <li
                  key={tag}
                  className="rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[11px] text-slate-600"
                >
                  {tagLabel(tag)}
                </li>
              ))}
            </ul>
          ) : null}
        </div>

        <div className="flex shrink-0 flex-col items-start gap-2 sm:items-end">
          <DeadlineBadge daysLeft={days_left} />
          <p className="text-xs text-slate-500">
            {deadline ? `Closes ${formatDate(deadline)}` : 'Deadline not published'}
          </p>
          <div className="mt-1 flex items-center gap-2">
            <button
              type="button"
              onClick={() => onSave(scholarship)}
              disabled={busy}
              className="btn-secondary"
            >
              {scholarship.application_status ? 'Tracked' : 'Save'}
            </button>
            <button
              type="button"
              onClick={() => onApply(scholarship)}
              disabled={busy}
              className="btn-primary"
            >
              Apply
              <span aria-hidden="true">↗</span>
            </button>
          </div>
        </div>
      </div>
    </article>
  )
}
