import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { ApiError, getToken, request, setToken } from '../lib/api'
import type { AuthResponse, User } from '../types'

interface AuthState {
  user: User | null
  /** True until the stored token has been checked against /auth/me. */
  loading: boolean
  signIn: (email: string, password: string) => Promise<void>
  signUp: (name: string, email: string, password: string) => Promise<void>
  signOut: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const queryClient = useQueryClient()

  // Restore the session on first load: a stored token may be expired.
  useEffect(() => {
    let cancelled = false
    if (!getToken()) {
      setLoading(false)
      return
    }
    request<User>('/auth/me')
      .then((me) => {
        if (!cancelled) setUser(me)
      })
      .catch((error) => {
        if (!(error instanceof ApiError)) console.error(error)
        setToken(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const adopt = useCallback(
    (response: AuthResponse) => {
      setToken(response.access_token)
      setUser(response.user)
      // Clear any cached data belonging to the previous account.
      queryClient.clear()
    },
    [queryClient],
  )

  const signIn = useCallback(
    async (email: string, password: string) => {
      adopt(
        await request<AuthResponse>('/auth/login', {
          method: 'POST',
          body: { email, password },
          auth: false,
        }),
      )
    },
    [adopt],
  )

  const signUp = useCallback(
    async (name: string, email: string, password: string) => {
      adopt(
        await request<AuthResponse>('/auth/signup', {
          method: 'POST',
          body: { name, email, password },
          auth: false,
        }),
      )
    },
    [adopt],
  )

  const signOut = useCallback(() => {
    setToken(null)
    setUser(null)
    queryClient.clear()
  }, [queryClient])

  const value = useMemo(
    () => ({ user, loading, signIn, signUp, signOut }),
    [user, loading, signIn, signUp, signOut],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext)
  if (context === null) throw new Error('useAuth must be used inside AuthProvider')
  return context
}
