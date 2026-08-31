import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api, apiGet, setAuthFailureHandler } from './api'
import { clearTokens, getAccess, setTokens } from './tokens'

const AuthContext = createContext(null)

// Mirrors the backend home_page redirect: ADMIN -> matrix, STAFF -> equipment.
export function defaultRouteFor(user) {
  return user?.is_admin ? '/personnel' : '/equipment'
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [isLoading, setIsLoading] = useState(true)

  const loadMe = useCallback(async () => {
    const me = await apiGet('/api/me/')
    setUser(me)
    return me
  }, [])

  // On app load: if a token is stored, validate it via /api/me/ (the api
  // interceptor will transparently refresh a stale access token).
  useEffect(() => {
    let active = true
    ;(async () => {
      if (getAccess()) {
        try {
          await loadMe()
        } catch {
          clearTokens()
          if (active) setUser(null)
        }
      }
      if (active) setIsLoading(false)
    })()
    return () => {
      active = false
    }
  }, [loadMe])

  // A refresh failure inside the api interceptor lands here.
  useEffect(() => {
    setAuthFailureHandler(() => setUser(null))
    return () => setAuthFailureHandler(null)
  }, [])

  const login = useCallback(
    async (username, password) => {
      const { data } = await api.post('/api/token/', { username, password })
      setTokens({ access: data.access, refresh: data.refresh })
      return loadMe()
    },
    [loadMe]
  )

  const logout = useCallback(() => {
    clearTokens()
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within <AuthProvider>')
  return ctx
}
