import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth, defaultRouteFor } from './lib/auth'
import ProtectedRoute from './components/ProtectedRoute'
import AppLayout from './components/AppLayout'
import { FullScreenSpinner } from './components/Spinner'

import LoginPage from './pages/LoginPage'
import PersonnelPage from './pages/PersonnelPage'
import CategoriesPage from './pages/CategoriesPage'
import StaffPage from './pages/StaffPage'
import EquipmentPage from './pages/EquipmentPage'
import MovementsPage from './pages/MovementsPage'
import RequestsPage from './pages/RequestsPage'
import TrainingsPage from './pages/TrainingsPage'
import ArchivedPage from './pages/ArchivedPage'

function RootRedirect() {
  const { user, isLoading } = useAuth()
  if (isLoading) return <FullScreenSpinner />
  return <Navigate to={user ? defaultRouteFor(user) : '/login'} replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />

          {/* authenticated shell */}
          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              {/* both roles */}
              <Route path="/equipment" element={<EquipmentPage />} />
              <Route path="/requests" element={<RequestsPage />} />
              <Route path="/trainings" element={<TrainingsPage />} />

              {/* ADMIN only */}
              <Route element={<ProtectedRoute allowedRoles={['ADMIN']} />}>
                <Route path="/personnel" element={<PersonnelPage />} />
                <Route path="/categories" element={<CategoriesPage />} />
                <Route path="/staff" element={<StaffPage />} />
                <Route path="/movements" element={<MovementsPage />} />
                <Route path="/archived" element={<ArchivedPage />} />
              </Route>
            </Route>
          </Route>

          <Route path="/" element={<RootRedirect />} />
          <Route path="*" element={<RootRedirect />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
