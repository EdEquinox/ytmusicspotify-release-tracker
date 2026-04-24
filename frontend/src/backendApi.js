const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001'

async function request(path, options = {}) {
  const response = await fetch(`${BACKEND_URL}${path}`, {
    headers: { 'content-type': 'application/json', ...(options.headers || {}) },
    ...options,
  })

  if (!response.ok) {
    let message = `HTTP Error ${response.status}`
    try {
      const json = await response.json()
      if (json.detail) message = json.detail
    } catch {}
    throw new Error(message)
  }

  if (response.status === 204) return null
  return response.json()
}

export const listArtists = () => request('/artistas')
export const refreshArtists = (onlyMissingImages = false) =>
  request(`/artistas/refresh?only_missing_images=${onlyMissingImages}`, { method: 'POST' })
export const createArtist = (payload) =>
  request('/artistas', { method: 'POST', body: JSON.stringify(payload) })
export const importArtists = (payload) =>
  request('/artistas/import', { method: 'POST', body: JSON.stringify(payload) })
export const deleteArtist = (artistId) => request(`/artistas/${artistId}`, { method: 'DELETE' })
export const searchSpotifyArtists = (query) =>
  request(`/spotify/artists/search?q=${encodeURIComponent(query)}`)
export const searchSpotifyTracks = (query, limit = 15) =>
  request(`/spotify/tracks/search?q=${encodeURIComponent(query)}&limit=${encodeURIComponent(limit)}`)
export const spotiflacDownloadSpotifyTrack = (spotifyUrl) =>
  request('/spotify/spotiflac-download', {
    method: 'POST',
    body: JSON.stringify({ spotify_url: spotifyUrl }),
  })
export const listReleases = (startDate, endDate) =>
  request(
    `/releases?start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`
  )
export const startReleasesSync = (startDate, endDate) =>
  request(
    `/releases/sync?start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`,
    { method: 'POST' }
  )
export const getReleasesSyncJob = (jobId) => request(`/releases/sync/${encodeURIComponent(jobId)}`)
export const startLocalReleasesFetch = ({ period = '', startDate = '', endDate = '' }) => {
  const params = new URLSearchParams()
  if (period) params.set('period', period)
  if (startDate) params.set('start_date', startDate)
  if (endDate) params.set('end_date', endDate)
  return request(`/releases/local/fetch?${params.toString()}`, { method: 'POST' })
}
export const getLocalReleasesFetchJob = (jobId) =>
  request(`/releases/local/fetch/${encodeURIComponent(jobId)}`)
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
export const getAlbumTracks = (albumId) =>
  request(`/spotify/albums/${encodeURIComponent(albumId)}/tracks`)

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
export const getSettings = () => request('/settings')
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
