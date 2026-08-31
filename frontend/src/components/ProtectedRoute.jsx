// §3 "Role-based nav visibility" — route-level gating. Unauthenticated ->
// /login. Wrong role or missing can_permanently_delete -> bounced to the
// user's own default route (the sidebar never links there anyway, so this
// only catches manual URL entry).
import { Navigate, Outlet } from 'react-router-dom'
import { useAuth, defaultRouteFor } from '../lib/auth'
import { FullScreenSpinner } from './Spinner'

export default function ProtectedRoute({ allowedRoles, requireCanDelete = false }) {
  const { user, isLoading } = useAuth()

  if (isLoading) return <FullScreenSpinner />
  if (!user) return <Navigate to="/login" replace />
  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to={defaultRouteFor(user)} replace />
  }
  if (requireCanDelete && !user.can_permanently_delete) {
    return <Navigate to={defaultRouteFor(user)} replace />
  }
  return <Outlet />
}
