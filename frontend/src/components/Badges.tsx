import { countdownLabel, sourceLabel, statusLabel, urgencyOf } from '../lib/format'
import type { AppStatus } from '../types'

const URGENCY_STYLES: Record<string, string> = {
  critical: 'bg-red-50 text-red-700 ring-red-200',
  soon: 'bg-amber-50 text-amber-800 ring-amber-200',
  normal: 'bg-slate-50 text-slate-600 ring-slate-200',
  none: 'bg-slate-50 text-slate-500 ring-slate-200',
  closed: 'bg-slate-100 text-slate-500 ring-slate-200',
}

/** Deadline countdown: red at <=3 days, amber at <=10, neutral otherwise. */
export function DeadlineBadge({ daysLeft }: { daysLeft: number | null }) {
  const urgency = urgencyOf(daysLeft)
  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-1 text-xs font-semibold ring-1 ring-inset ${URGENCY_STYLES[urgency]}`}
    >
      {countdownLabel(daysLeft)}
    </span>
  )
}

const SOURCE_STYLES: Record<string, string> = {
  nsp: 'bg-accent-50 text-accent-700 ring-accent-200',
  buddy4study: 'bg-teal-50 text-teal-700 ring-teal-200',
  vidyasaarathi: 'bg-violet-50 text-violet-700 ring-violet-200',
  manual: 'bg-slate-50 text-slate-600 ring-slate-200',
}

export function SourceBadge({ source }: { source: string }) {
  const style = SOURCE_STYLES[source] ?? SOURCE_STYLES.manual
  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${style}`}
    >
      {sourceLabel(source)}
    </span>
  )
}

const STATUS_STYLES: Record<AppStatus, string> = {
  saved: 'bg-slate-100 text-slate-700 ring-slate-200',
  applied: 'bg-accent-50 text-accent-700 ring-accent-200',
  under_review: 'bg-amber-50 text-amber-800 ring-amber-200',
  awarded: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  rejected: 'bg-red-50 text-red-700 ring-red-200',
}

export function StatusPill({ status }: { status: AppStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${STATUS_STYLES[status]}`}
    >
      {statusLabel(status)}
    </span>
  )
}
