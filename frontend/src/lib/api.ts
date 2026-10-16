/**
 * Thin fetch wrapper.
 *
 * The frontend always calls relative /api paths: in production Vercel serves
 * the API from the same origin, and in dev Vite proxies to uvicorn. So there is
 * no base URL to configure and no CORS to arrange.
 */
const TOKEN_KEY = 'scholartrack.token'

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    // Private browsing or blocked storage: stay logged out rather than crash.
    return null
  }
}

export function setToken(token: string | null): void {
  try {
    if (token === null) localStorage.removeItem(TOKEN_KEY)
    else localStorage.setItem(TOKEN_KEY, token)
  } catch {
    /* ignore: the session simply will not persist across reloads */
  }
}

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** Pull a readable message out of FastAPI's error shapes. */
function messageFrom(status: number, body: unknown): string {
  if (typeof body === 'string' && body) return body
  if (body && typeof body === 'object') {
    const detail = (body as { detail?: unknown }).detail
    if (typeof detail === 'string') return detail
    // 422 validation errors arrive as a list of {loc, msg}.
    if (Array.isArray(detail)) {
      const parts = detail
        .map((d) => {
          if (d && typeof d === 'object') {
            const loc = (d as { loc?: unknown[] }).loc
            const msg = (d as { msg?: string }).msg ?? ''
            const field = Array.isArray(loc) ? loc.slice(1).join('.') : ''
            return field ? `${field}: ${msg}` : msg
          }
          return String(d)
        })
        .filter(Boolean)
      if (parts.length) return parts.join('; ')
    }
  }
  if (status === 401) return 'Your session has expired. Please sign in again.'
  return `Request failed (${status})`
}

interface RequestOptions {
  method?: string
  body?: unknown
  /** Set false for the auth endpoints, which have no token yet. */
  auth?: boolean
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, auth = true } = options
  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (auth) {
    const token = getToken()
    if (token) headers.Authorization = `Bearer ${token}`
  }

  const response = await fetch(`/api${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  })

  if (response.status === 204) return undefined as T

  const text = await response.text()
  let parsed: unknown = text
  if (text) {
    try {
      parsed = JSON.parse(text)
    } catch {
      /* keep the raw text for the error message */
    }
  }

  if (!response.ok) {
    if (response.status === 401 && auth) {
      // The token is gone or expired; drop it so the app redirects to sign-in.
      setToken(null)
    }
    throw new ApiError(response.status, messageFrom(response.status, parsed))
  }

  return parsed as T
}

/** Build a query string, skipping empty values and repeating array params. */
export function query(params: Record<string, string | number | boolean | string[] | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === '' || value === false) continue
    if (Array.isArray(value)) {
      for (const item of value) if (item) search.append(key, item)
    } else {
      search.set(key, String(value))
    }
  }
  const qs = search.toString()
  return qs ? `?${qs}` : ''
}
