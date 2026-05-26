const STORAGE_KEY = 'session_access_token'

/** @returns {string} */
export function getSessionToken() {
  try {
    return (sessionStorage.getItem(STORAGE_KEY) || '').trim()
  } catch {
    return ''
  }
}

/** @param {string} token */
export function setSessionToken(token) {
  const value = (token || '').trim()
  try {
    if (value) sessionStorage.setItem(STORAGE_KEY, value)
    else sessionStorage.removeItem(STORAGE_KEY)
  } catch {
    // private browsing / blocked storage
  }
}

export function clearSessionToken() {
  setSessionToken('')
}

/** @returns {Record<string, string>} */
export function apiAuthHeaders() {
  const token = getSessionToken()
  if (!token) return {}
  return { authorization: `Bearer ${token}` }
}
