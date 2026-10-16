import { Navigate, useLocation } from 'react-router-dom'

import { useAuth } from '../context/AuthContext'
import { Spinner } from './Spinner'

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()

  // Wait for the stored token to be validated before deciding.
  if (loading) return <Spinner label="Loading your account" />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return <>{children}</>
}
