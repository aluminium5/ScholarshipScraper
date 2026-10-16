/** Date and countdown helpers shared by the dashboard and tracker. */

const DATE_FMT = new Intl.DateTimeFormat('en-IN', {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
})

/** Parse a plain ISO date (YYYY-MM-DD) as local, not UTC. */
function parseIsoDate(iso: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso)
  if (!match) {
    const fallback = new Date(iso)
    return Number.isNaN(fallback.getTime()) ? null : fallback
  }
  const [, y, m, d] = match
  return new Date(Number(y), Number(m) - 1, Number(d))
}

export function formatDate(iso: string | null): string {
  if (!iso) return '—'
  const date = parseIsoDate(iso)
  return date ? DATE_FMT.format(date) : '—'
}

/** "3 days left", "Today", "Closed 2 days ago". */
export function countdownLabel(daysLeft: number | null): string {
  if (daysLeft === null) return 'No deadline listed'
  if (daysLeft < 0) {
    const ago = Math.abs(daysLeft)
    return `Closed ${ago} day${ago === 1 ? '' : 's'} ago`
  }
  if (daysLeft === 0) return 'Closes today'
  if (daysLeft === 1) return '1 day left'
  return `${daysLeft} days left`
}

export type Urgency = 'critical' | 'soon' | 'normal' | 'none' | 'closed'

/** Red at 3 days or fewer, amber at 10 or fewer, neutral otherwise. */
export function urgencyOf(daysLeft: number | null): Urgency {
  if (daysLeft === null) return 'none'
  if (daysLeft < 0) return 'closed'
  if (daysLeft <= 3) return 'critical'
  if (daysLeft <= 10) return 'soon'
  return 'normal'
}

/** "3h ago", "2d ago" — for the last-refresh line. */
export function relativeTime(iso: string | null): string {
  if (!iso) return 'never'
  const then = new Date(iso)
  if (Number.isNaN(then.getTime())) return 'never'
  const seconds = Math.floor((Date.now() - then.getTime()) / 1000)
  if (seconds < 60) return 'just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

const SOURCE_LABELS: Record<string, string> = {
  nsp: 'NSP',
  buddy4study: 'Buddy4Study',
  vidyasaarathi: 'Vidyasaarathi',
  manual: 'Curated',
}

export function sourceLabel(source: string): string {
  return SOURCE_LABELS[source] ?? source
}

const LEVEL_LABELS: Record<string, string> = {
  school: 'School',
  ug: 'Undergraduate',
  pg: 'Postgraduate',
  phd: 'PhD',
  any: 'Any level',
}

export function levelLabel(level: string): string {
  return LEVEL_LABELS[level] ?? level
}

const TAG_LABELS: Record<string, string> = {
  girls: 'Girls',
  merit: 'Merit',
  need: 'Need-based',
  sc_st: 'SC/ST',
  obc: 'OBC',
  minority: 'Minority',
  pwd: 'PwD',
  renewal: 'Renewal only',
  technical: 'Technical',
  research: 'Research',
}

export function tagLabel(tag: string): string {
  return TAG_LABELS[tag] ?? tag.replace(/_/g, ' ')
}

const STATUS_LABELS: Record<string, string> = {
  saved: 'Saved',
  applied: 'Applied',
  under_review: 'Under review',
  awarded: 'Awarded',
  rejected: 'Rejected',
}

export function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status
}
