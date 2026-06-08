const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001'

/**
 * @param {string} path
 * @param {RequestInit} [options]
 * @returns {Promise<any>}
 */
async function request(path, options = {}) {
  let response
  try {
    response = await fetch(`${BACKEND_URL}${path}`, {
      headers: { 'content-type': 'application/json', ...(options.headers || {}) },
      ...options,
    })
  } catch (err) {
    const hint =
      ' Verifica se o backend está a correr (na pasta backend: uvicorn main:app --reload --port 8001) e se REACT_APP_BACKEND_URL aponta para o URL certo.'
    const msg = err instanceof Error ? err.message : String(err)
    throw new Error(`Sem ligação ao servidor (${BACKEND_URL}): ${msg}.${hint}`)
  }

  if (!response.ok) {
    let message = `HTTP Error ${response.status}`
    try {
      const json = await response.json()
      if (json.detail) message = json.detail
    } catch {}
    throw new Error(message)
  }

  if (response.status === 204) return null
  const raw = await response.text()
  if (!raw.trim()) {
    throw new Error(
      `Resposta vazia de ${BACKEND_URL}${path} (HTTP ${response.status}). O uvicorn pode ter crashado ou outro programa está na mesma porta. Testa: curl -sS ${BACKEND_URL}/health`
    )
  }
  try {
    return JSON.parse(raw)
  } catch {
    throw new Error(`Resposta não-JSON de ${BACKEND_URL}${path} (primeiros caracteres: ${raw.slice(0, 80)}…)`)
  }
}

export const listArtists = () => request('/artistas')
export const refreshArtists = (onlyMissingImages = false) =>
  request(`/artistas/refresh?only_missing_images=${onlyMissingImages}`, { method: 'POST' })
export const createArtist = (payload) =>
  request('/artistas', { method: 'POST', body: JSON.stringify(payload) })
export const importArtists = (payload) =>
  request('/artistas/import', { method: 'POST', body: JSON.stringify(payload) })
export const deleteArtist = (artistId) => request(`/artistas/${artistId}`, { method: 'DELETE' })

export const patchArtistTidalId = (artistId, tidalId) =>
  request(`/artistas/${encodeURIComponent(artistId)}`, {
    method: 'PATCH',
    body: JSON.stringify({ tidal_id: tidalId == null || tidalId === '' ? null : String(tidalId).trim() }),
  })
export const searchTidalArtists = (query, limit = 15) =>
  request(
    `/releases/tidal/artists/search?q=${encodeURIComponent(query)}&limit=${encodeURIComponent(limit)}`
  )
export const searchTidalTracks = (query, limit = 15) =>
  request(
    `/releases/tidal/tracks/search?q=${encodeURIComponent(query)}&limit=${encodeURIComponent(limit)}`
  )
export const spotiflacDownloadTidalTrack = ({ tidal_url, artist_name = '', track_name = '' }) =>
  request('/releases/tidal/spotiflac-download', {
    method: 'POST',
    body: JSON.stringify({ tidal_url, artist_name, track_name }),
  })
export const startLocalReleasesFetch = ({ period = '', startDate = '', endDate = '' }) => {
  const params = new URLSearchParams()
  if (period) params.set('period', period)
  if (startDate) params.set('start_date', startDate)
  if (endDate) params.set('end_date', endDate)
  return request(`/releases/local/fetch?${params.toString()}`, { method: 'POST' })
}
export const getLocalReleasesFetchJob = (jobId) =>
  request(`/releases/local/fetch/${encodeURIComponent(jobId)}`)

export const getTidalSession = () => request('/releases/tidal/session')

export const startTidalDeviceLogin = () =>
  request('/releases/tidal/device/start', { method: 'POST' })

export const getTidalDeviceStatus = () => request('/releases/tidal/device/status')

export const getTidalAlbumTracks = (albumId) =>
  request(`/releases/tidal/albums/${encodeURIComponent(albumId)}/tracks`)
export const listLocalReleases = () => request('/releases/local')
export const fetchArtistReleases = (artistId, period, force = false) =>
  request(
    `/artistas/${encodeURIComponent(artistId)}/releases/fetch?period=${encodeURIComponent(period)}&force=${force}`,
    {
      method: 'POST',
    }
  )
export const listCsvReleases = () => request('/csv/releases')
export const addReleaseToCsv = (releaseId) =>
  request('/csv/releases', { method: 'POST', body: JSON.stringify({ release_id: releaseId }) })
export const addTrackToCsv = (track) =>
  request('/csv/releases', { method: 'POST', body: JSON.stringify(track) })
export const removeReleaseFromCsv = (releaseId) =>
  request(`/csv/releases/${encodeURIComponent(releaseId)}`, { method: 'DELETE' })
export const listErrors = () => request('/erros')
export const resolveError = (errorId) =>
  request(`/erros/${encodeURIComponent(errorId)}/resolve`, { method: 'POST' })
export const deleteError = (errorId) => request(`/erros/${errorId}`, { method: 'DELETE' })
export const updateErrorLinks = (errorId, payload) =>
  request(`/erros/${encodeURIComponent(errorId)}/links`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
export const listHistorico = () => request('/historico')
/** @returns {Promise<Record<string, unknown>>} */
export const getSettings = () => request('/settings')
/** @param {Record<string, unknown>} payload */
export const updateSettings = (payload) =>
  request('/settings', { method: 'PUT', body: JSON.stringify(payload) })
export const importYTMusicAuth = (authJson) =>
  request('/settings/ytmusic-auth/import', {
    method: 'POST',
    body: JSON.stringify({ auth_json: authJson }),
  })
export const validateYTMusicAuth = () =>
  request('/settings/ytmusic-auth/validate', {
    method: 'POST',
  })
export const completeReverseSpotifyOAuth = (responseUrl) =>
  request('/settings/reverse-spotify-oauth/complete', {
    method: 'POST',
    body: JSON.stringify({ response_url: responseUrl }),
  })
