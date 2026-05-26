import { useCallback, useEffect, useState } from 'react'
import { clearSessionToken, getSessionToken, setSessionToken } from 'apiAuth'

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001'

/**
 * @param {{ children: import('react').ReactNode }} props
 */
function ApiAccessGate({ children }) {
  const [ready, setReady] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [checking, setChecking] = useState(true)

  const verifySession = useCallback(async (token) => {
    const response = await fetch(`${BACKEND_URL}/auth/verify`, {
      headers: { authorization: `Bearer ${token}` },
    })
    if (response.status === 401) {
      throw new Error('Sessão expirada. Inicia sessão outra vez.')
    }
    if (!response.ok) {
      throw new Error(`Não foi possível validar a sessão (HTTP ${response.status}).`)
    }
  }, [])

  const probeAuth = useCallback(async () => {
    setChecking(true)
    setError('')
    try {
      const health = await fetch(`${BACKEND_URL}/health`)
      if (!health.ok) {
        throw new Error(`Backend inacessível (HTTP ${health.status}).`)
      }

      const token = getSessionToken()
      if (token) {
        await verifySession(token)
        setReady(true)
        return
      }

      const openCheck = await fetch(`${BACKEND_URL}/auth/verify`)
      if (openCheck.status === 401) {
        setReady(false)
        return
      }
      if (!openCheck.ok) {
        throw new Error(`Não foi possível contactar o backend (HTTP ${openCheck.status}).`)
      }
      setReady(true)
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      if (message.includes('Sessão expirada')) {
        clearSessionToken()
      }
      setReady(false)
      setError(message)
    } finally {
      setChecking(false)
    }
  }, [verifySession])

  useEffect(() => {
    probeAuth()
  }, [probeAuth])

  const onSubmit = async (event) => {
    event.preventDefault()
    setError('')
    setChecking(true)
    try {
      const user = username.trim()
      const pass = password
      if (!user || !pass) {
        setError('Preenche utilizador e palavra-passe.')
        return
      }

      const response = await fetch(`${BACKEND_URL}/auth/login`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ username: user, password: pass }),
      })

      if (response.status === 401) {
        throw new Error('Utilizador ou palavra-passe incorretos.')
      }
      if (response.status === 503) {
        throw new Error('Login por utilizador não está configurado no servidor (APP_USERNAME/APP_PASSWORD).')
      }
      if (!response.ok) {
        let message = `Erro ao iniciar sessão (HTTP ${response.status}).`
        try {
          const json = await response.json()
          if (json.detail) message = json.detail
        } catch {}
        throw new Error(message)
      }

      const data = await response.json()
      const token = (data.access_token || '').trim()
      if (!token) {
        throw new Error('Resposta de login inválida.')
      }

      setSessionToken(token)
      setReady(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setChecking(false)
    }
  }

  if (ready) return children

  return (
    <div className="LocalPage ApiAccessGate">
      <div className="LocalPanel">
        <h1 className="title is-5 has-text-light">Iniciar sessão</h1>
        <p className="has-text-grey-light">
          Usa a conta definida no stack (<code>APP_USERNAME</code> / <code>APP_PASSWORD</code>). O{' '}
          <code>API_TOKEN</code> fica só para os workers — não aparece no browser.
        </p>
        <form onSubmit={onSubmit} className="mt-4">
          <div className="field">
            <label className="label has-text-grey-light" htmlFor="login-username">
              Utilizador
            </label>
            <div className="control">
              <input
                id="login-username"
                className="input"
                type="text"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                disabled={checking}
              />
            </div>
          </div>
          <div className="field">
            <label className="label has-text-grey-light" htmlFor="login-password">
              Palavra-passe
            </label>
            <div className="control">
              <input
                id="login-password"
                className="input"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={checking}
              />
            </div>
          </div>
          {error ? <p className="help is-danger">{error}</p> : null}
          <button type="submit" className="button is-primary mt-3" disabled={checking}>
            {checking ? 'A verificar…' : 'Entrar'}
          </button>
        </form>
      </div>
    </div>
  )
}

export default ApiAccessGate
