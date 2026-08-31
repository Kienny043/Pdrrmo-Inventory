import axios from 'axios'
import { getAccess, getRefresh, setTokens, clearTokens } from './tokens'

const BASE = import.meta.env.VITE_API_BASE || '' // '' = same origin (dev proxy / prod whitenoise)

export const api = axios.create({ baseURL: BASE })

// The AuthProvider registers a handler so a dead session can force the UI
// back to a logged-out state without this module importing React.
let onAuthFailure = null
export const setAuthFailureHandler = (fn) => {
  onAuthFailure = fn
}

// Turn a DRF error body into a single clean message.
function messageFrom(error) {
  const data = error.response?.data
  if (!data) return error.message || 'Request failed'
  if (typeof data === 'string') return data
  if (data.detail) return String(data.detail)
  const key = Object.keys(data)[0]
  if (!key) return 'Request failed'
  const v = data[key]
  const msg = Array.isArray(v) ? v[0] : v
  return key === 'non_field_errors' ? String(msg) : `${key}: ${msg}`
}

function normalize(error) {
  const e = new Error(messageFrom(error))
  e.status = error.response?.status
  e.data = error.response?.data
  return e
}

api.interceptors.request.use((config) => {
  const token = getAccess()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

let refreshInFlight = null

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config || {}
    const status = error.response?.status
    const isAuthCall = (original.url || '').includes('/api/token/')

    if (status === 401 && !original._retried && !isAuthCall && getRefresh()) {
      original._retried = true
      try {
        refreshInFlight =
          refreshInFlight ||
          axios.post(`${BASE}/api/token/refresh/`, { refresh: getRefresh() })
        const { data } = await refreshInFlight
        refreshInFlight = null
        setTokens({ access: data.access })
        original.headers = original.headers || {}
        original.headers.Authorization = `Bearer ${data.access}`
        return api(original)
      } catch {
        refreshInFlight = null
        clearTokens()
        if (onAuthFailure) onAuthFailure()
        return Promise.reject(normalize(error))
      }
    }
    return Promise.reject(normalize(error))
  }
)

export const apiGet = (url, config) => api.get(url, config).then((r) => r.data)
export const apiPost = (url, body, config) => api.post(url, body, config).then((r) => r.data)
export const apiPatch = (url, body, config) => api.patch(url, body, config).then((r) => r.data)
export const apiDelete = (url, config) => api.delete(url, config).then((r) => r.data)
