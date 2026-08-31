import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useAuth, defaultRouteFor } from '../lib/auth'
import Button from '../components/Button'
import ErrorBanner from '../components/ErrorBanner'
import { Field, INPUT_CLASS } from '../components/Field'
import { FullScreenSpinner } from '../components/Spinner'

export default function LoginPage() {
  const { user, isLoading, login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  if (isLoading) return <FullScreenSpinner />
  if (user) return <Navigate to={defaultRouteFor(user)} replace />

  const onSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      const me = await login(username.trim(), password)
      navigate(defaultRouteFor(me), { replace: true })
    } catch (err) {
      setError(err.message || 'Login failed.')
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-pd-gray px-4">
      <div className="bg-white border border-pd-border rounded-2xl shadow-sm w-full max-w-sm p-8">
        <div className="flex items-center gap-2 mb-6">
          <div className="h-9 w-9 rounded-lg bg-pd-navy flex items-center justify-center text-white text-xs font-bold">
            PD
          </div>
          <div>
            <div
              className="text-sm font-bold text-pd-text-primary tracking-wide"
              style={{ fontFamily: "'Sora', sans-serif" }}
            >
              PDRRMO
            </div>
            <div className="text-[11px] text-pd-text-secondary">
              Inventory &amp; Training Matrix
            </div>
          </div>
        </div>

        <h1
          className="text-lg font-bold text-pd-text-primary mb-4"
          style={{ fontFamily: "'Sora', sans-serif" }}
        >
          Sign in
        </h1>

        <form className="flex flex-col gap-4" onSubmit={onSubmit}>
          {error && <ErrorBanner>{error}</ErrorBanner>}
          <Field label="Username" required>
            <input
              className={INPUT_CLASS}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              autoFocus
              required
            />
          </Field>
          <Field label="Password" required>
            <input
              type="password"
              className={INPUT_CLASS}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </Field>
          <Button type="submit" variant="primary" disabled={submitting} className="mt-1">
            {submitting ? 'Signing in…' : 'Sign in'}
          </Button>
        </form>
      </div>
    </div>
  )
}
