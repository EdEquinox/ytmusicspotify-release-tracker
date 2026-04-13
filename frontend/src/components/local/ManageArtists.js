import { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Button, Input, VerticalLayout, Header, Content, ButtonLink } from 'components/common'
import {
  createArtist,
  deleteArtist,
  getSettings,
  listArtists,
  refreshArtists,
  searchSpotifyArtists,
} from 'backendApi'

const FALLBACK_SPOTIFY_CLIENT_ID = process.env.REACT_APP_SPOTIFY_CLIENT_ID || ''
const FALLBACK_SPOTIFY_REDIRECT_URI =
  process.env.REACT_APP_SPOTIFY_REDIRECT_URI || `${window.location.origin}/artists`
const SPOTIFY_IMPORT_STATE = 'spotify-artists-import'
const SPOTIFY_CODE_VERIFIER_KEY = 'spotifyImportCodeVerifier'

function generateCodeVerifier(length = 64) {
  const charset = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._~'
  const random = window.crypto.getRandomValues(new Uint8Array(length))
  return Array.from(random)
    .map((value) => charset[value % charset.length])
    .join('')
}

async function createCodeChallenge(codeVerifier) {
  const data = new TextEncoder().encode(codeVerifier)
  const digest = await window.crypto.subtle.digest('SHA-256', data)
  const bytes = new Uint8Array(digest)
  let binary = ''
  for (const byte of bytes) binary += String.fromCharCode(byte)
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

async function exchangeCodeForToken(code, clientId, redirectUri, codeVerifier) {
  const body = new URLSearchParams({
    grant_type: 'authorization_code',
    client_id: clientId,
    code,
    redirect_uri: redirectUri,
    code_verifier: codeVerifier,
  }).toString()

  const response = await fetch('https://accounts.spotify.com/api/token', {
    method: 'POST',
    headers: { 'content-type': 'application/x-www-form-urlencoded' },
    body,
  })

  if (!response.ok) {
    throw new Error('Falha ao trocar codigo por token no Spotify.')
  }

  const json = await response.json()
  if (!json.access_token) throw new Error('Resposta invalida do Spotify (sem access token).')
  return json.access_token
}

async function getFollowedArtists(accessToken) {
  const artists = []
  let nextUrl = 'https://api.spotify.com/v1/me/following?type=artist&limit=50'

  while (nextUrl) {
    const response = await fetch(nextUrl, {
      headers: { authorization: `Bearer ${accessToken}` },
    })

    if (!response.ok) throw new Error('Falha ao obter artistas seguidos da conta Spotify.')
    const payload = await response.json()
    const page = payload.artists
    for (const item of page.items) {
      artists.push({
        id: item.id,
        name: item.name,
        image_url: ((item.images || [])[0] || {}).url || null,
      })
    }
    nextUrl = page.next
  }

  return artists
}

function ManageArtists() {
  const location = useLocation()
  const navigate = useNavigate()
  const [artists, setArtists] = useState([])
  const [query, setQuery] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [searchLoading, setSearchLoading] = useState(false)
  const [refreshingArtists, setRefreshingArtists] = useState(false)
  const [importing, setImporting] = useState(false)
  const [loading, setLoading] = useState(true)
  const [spotifyClientId, setSpotifyClientId] = useState(FALLBACK_SPOTIFY_CLIENT_ID)
  const [spotifyRedirectUri, setSpotifyRedirectUri] = useState(FALLBACK_SPOTIFY_REDIRECT_URI)
  const [error, setError] = useState('')
  const [infoMessage, setInfoMessage] = useState('')

  const loadArtists = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await listArtists()
      setArtists(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadArtists()
  }, [])

  useEffect(() => {
    async function loadOAuthSettings() {
      try {
        const settings = await getSettings()
        if (settings.spotify_oauth_client_id) setSpotifyClientId(settings.spotify_oauth_client_id)
        if (settings.spotify_oauth_redirect_uri) setSpotifyRedirectUri(settings.spotify_oauth_redirect_uri)
      } catch {
        // Keep env fallback when settings are unavailable.
      }
    }
    loadOAuthSettings()
  }, [])

  useEffect(() => {
    const runImportCallback = async () => {
      const params = new URLSearchParams(location.search)
      const code = params.get('code')
      const state = params.get('state')
      if (!code || state !== SPOTIFY_IMPORT_STATE) return

      const codeVerifier = sessionStorage.getItem(SPOTIFY_CODE_VERIFIER_KEY)
      if (!codeVerifier) {
        setError('Codigo verificador em falta. Tenta importar novamente.')
        navigate('/artists', { replace: true })
        return
      }

      setImporting(true)
      setError('')
      setInfoMessage('')

      try {
        const accessToken = await exchangeCodeForToken(
          code,
          spotifyClientId,
          spotifyRedirectUri,
          codeVerifier
        )
        const followedArtists = await getFollowedArtists(accessToken)

        let added = 0
        let skipped = 0
        for (const artist of followedArtists) {
          try {
            await createArtist(artist)
            added += 1
          } catch (err) {
            if (String(err.message).toLowerCase().includes('already exists')) skipped += 1
            else throw err
          }
        }

        await loadArtists()
        setInfoMessage(`Importacao concluida: ${added} adicionados, ${skipped} ja existentes.`)
      } catch (err) {
        setError(err.message)
      } finally {
        sessionStorage.removeItem(SPOTIFY_CODE_VERIFIER_KEY)
        setImporting(false)
        navigate('/artists', { replace: true })
      }
    }

    runImportCallback()
  }, [location.search, spotifyClientId, spotifyRedirectUri])

  const onDelete = async (artistId) => {
    setError('')
    try {
      await deleteArtist(artistId)
      await loadArtists()
    } catch (err) {
      setError(err.message)
    }
  }

  const onSearch = async (event) => {
    if (event?.preventDefault) event.preventDefault()
    if (searchQuery.trim().length < 2) {
      setSearchResults([])
      setError('A pesquisa deve ter pelo menos 2 caracteres.')
      return
    }

    setSearchLoading(true)
    setError('')
    try {
      const data = await searchSpotifyArtists(searchQuery.trim())
      setSearchResults(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setSearchLoading(false)
    }
  }

  const onAddFromSearch = async (artist) => {
    setError('')
    try {
      await createArtist({ id: artist.id, name: artist.name, image_url: artist.image_url || null })
      await loadArtists()
    } catch (err) {
      setError(err.message)
    }
  }

  const onImportFollowedArtists = async () => {
    if (!spotifyClientId) {
      setError('Define Spotify OAuth Client ID em Settings para usar a importacao.')
      return
    }

    try {
      setError('')
      setInfoMessage('')
      setImporting(true)

      const codeVerifier = generateCodeVerifier()
      const codeChallenge = await createCodeChallenge(codeVerifier)
      sessionStorage.setItem(SPOTIFY_CODE_VERIFIER_KEY, codeVerifier)

      const authParams = new URLSearchParams({
        response_type: 'code',
        client_id: spotifyClientId,
        scope: 'user-follow-read',
        redirect_uri: spotifyRedirectUri,
        code_challenge_method: 'S256',
        code_challenge: codeChallenge,
        state: SPOTIFY_IMPORT_STATE,
      })

      window.location.assign(`https://accounts.spotify.com/authorize?${authParams.toString()}`)
    } catch (err) {
      setImporting(false)
      setError(err.message)
    }
  }

  const onRefreshArtistsInfo = async () => {
    setError('')
    setInfoMessage('')
    setRefreshingArtists(true)
    try {
      const result = await refreshArtists(true)
      await loadArtists()
      setInfoMessage(`Atualizacao concluida: ${result.updated}/${result.total} artistas atualizados.`)
    } catch (err) {
      setError(err.message)
    } finally {
      setRefreshingArtists(false)
    }
  }

  const filteredArtists = useMemo(() => {
    const lowerQuery = query.trim().toLowerCase()
    if (!lowerQuery) return artists
    return artists.filter(
      (artist) =>
        artist.name.toLowerCase().includes(lowerQuery) || artist.id.toLowerCase().includes(lowerQuery)
    )
  }, [artists, query])

  return (
    <VerticalLayout>
      <Header title="Gerir Artistas">
        <div className="Header__right">
          <ButtonLink to="/" title="Releases" icon="fas fa-music" compact>
            Releases
          </ButtonLink>
          <ButtonLink to="/errors" title="Erros de sincronizacao" icon="fas fa-triangle-exclamation" compact>
            Erros
          </ButtonLink>
          <ButtonLink to="/settings" title="Settings" icon="fas fa-gear" compact>
            Settings
          </ButtonLink>
          <ButtonLink to="/setup" title="Guia de configuracao" icon="fas fa-circle-info" compact>
            Guia
          </ButtonLink>
        </div>
      </Header>
      <Content>
        <div className="LocalPage">
        <div className="LocalPanel LocalPanel--toolbar mb-5">
          <div className="LocalTopRow">
            <div className="LocalTopRow__actions">
              <Button onClick={onImportFollowedArtists} primary disabled={importing}>
                {importing ? 'A importar...' : 'Importar artistas'}
              </Button>
              <Button onClick={onRefreshArtistsInfo} primary disabled={refreshingArtists || loading}>
                {refreshingArtists ? 'A atualizar...' : 'Atualizar info artistas'}
              </Button>
            </div>
            <div className="LocalTopRow__search">
              <Input
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder="Ex: Radiohead"
              />
            </div>
            <div className="LocalTopRow__actions">
              <Button onClick={onSearch} primary disabled={searchLoading || searchQuery.trim().length < 2}>
                {searchLoading ? 'A pesquisar...' : 'Pesquisar'}
              </Button>
            </div>
          </div>
        </div>

        {searchResults.length > 0 && (
          <div className="LocalArtistGrid mb-5">
            {searchResults.map((artist) => (
              <article className="LocalArtistCardCompact" key={artist.id}>
                <div className="LocalArtistRow__media">
                  {artist.image_url ? (
                    <img className="LocalArtistRow__avatar" src={artist.image_url} alt={artist.name} />
                  ) : (
                    <div className="LocalArtistRow__avatar LocalArtistRow__avatar--placeholder" />
                  )}
                  <div>
                    <p className="LocalArtistRow__name">{artist.name}</p>
                    <code className="LocalArtistRow__id">{artist.id}</code>
                  </div>
                </div>
                <Button
                  onClick={() => onAddFromSearch(artist)}
                  className="LocalActionButton LocalActionButton--primary"
                >
                  Adicionar
                </Button>
              </article>
            ))}
          </div>
        )}

        <div className="LocalPanel">
        <div className="field">
          <label className="label has-text-light">Filtrar artistas</label>
          <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Pesquisar por nome ou id" />
        </div>
        </div>

        {error && <p className="has-text-danger">{error}</p>}
        {infoMessage && <p className="has-text-success">{infoMessage}</p>}
        {loading && <p className="has-text-grey">A carregar...</p>}
        {!loading && !filteredArtists.length && <p className="has-text-grey">Sem artistas guardados.</p>}

        {!loading && filteredArtists.length > 0 && (
          <div className="LocalArtistGrid">
            {filteredArtists.map((artist) => (
              <article className="LocalArtistCardCompact" key={artist.id}>
                <div className="LocalArtistRow__media">
                  {artist.image_url ? (
                    <img className="LocalArtistRow__avatar" src={artist.image_url} alt={artist.name} />
                  ) : (
                    <div className="LocalArtistRow__avatar LocalArtistRow__avatar--placeholder" />
                  )}
                  <div>
                    <p className="LocalArtistRow__name">{artist.name}</p>
                    <code className="LocalArtistRow__id">{artist.id}</code>
                  </div>
                </div>
                <div className="LocalArtistRow__actions">
                  <Button onClick={() => onDelete(artist.id)} className="LocalActionButton">
                    Apagar
                  </Button>
                </div>
              </article>
            ))}
          </div>
        )}
        </div>
      </Content>
    </VerticalLayout>
  )
}

export default ManageArtists
