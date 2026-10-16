import { useEffect, useRef, useState } from 'react'

/**
 * Copies one portfolio field. This is the point of the portfolio page: the
 * student pastes these values into application forms.
 */
export function CopyButton({ value, label }: { value: string | null; label: string }) {
  const [copied, setCopied] = useState(false)
  const timer = useRef<number | undefined>(undefined)

  useEffect(() => () => window.clearTimeout(timer.current), [])

  const empty = value === null || value.trim() === ''

  async function copy() {
    if (empty) return
    try {
      await navigator.clipboard.writeText(value!)
    } catch {
      // Clipboard API needs a secure context; fall back to a temp textarea.
      const scratch = document.createElement('textarea')
      scratch.value = value!
      scratch.setAttribute('readonly', '')
      scratch.style.position = 'fixed'
      scratch.style.opacity = '0'
      document.body.appendChild(scratch)
      scratch.select()
      try {
        document.execCommand('copy')
      } catch {
        return
      } finally {
        document.body.removeChild(scratch)
      }
    }
    setCopied(true)
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => setCopied(false), 1400)
  }

  return (
    <button
      type="button"
      onClick={copy}
      disabled={empty}
      title={empty ? `Nothing to copy for ${label}` : `Copy ${label}`}
      aria-label={empty ? `Nothing to copy for ${label}` : `Copy ${label}`}
      className="btn-ghost shrink-0 px-2 py-1 text-xs"
    >
      {copied ? (
        <span className="font-medium text-emerald-600">Copied</span>
      ) : (
        <svg
          viewBox="0 0 20 20"
          fill="currentColor"
          className="h-4 w-4"
          aria-hidden="true"
        >
          <path d="M7 5a2 2 0 012-2h6a2 2 0 012 2v8a2 2 0 01-2 2H9a2 2 0 01-2-2V5z" />
          <path d="M5 7a2 2 0 00-2 2v6a2 2 0 002 2h5a2 2 0 002-2v-1H9a3 3 0 01-3-3V7H5z" />
        </svg>
      )}
    </button>
  )
}
