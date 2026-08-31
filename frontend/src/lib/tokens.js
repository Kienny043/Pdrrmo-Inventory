// JWT storage. localStorage keeps the session across full page reloads;
// the AuthProvider re-validates on load by calling /api/me/.
const ACCESS_KEY = 'inv_access'
const REFRESH_KEY = 'inv_refresh'

export const getAccess = () => {
  try {
    return localStorage.getItem(ACCESS_KEY)
  } catch {
    return null
  }
}

export const getRefresh = () => {
  try {
    return localStorage.getItem(REFRESH_KEY)
  } catch {
    return null
  }
}

export const setTokens = ({ access, refresh } = {}) => {
  try {
    if (access) localStorage.setItem(ACCESS_KEY, access)
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh)
  } catch {
    /* private mode / storage disabled — session just won't persist */
  }
}

export const clearTokens = () => {
  try {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  } catch {
    /* ignore */
  }
}
