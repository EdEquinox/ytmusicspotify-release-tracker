import { useEffect, useMemo, useState } from 'react'
import { Button, ButtonLink, Content, Header, Input, VerticalLayout } from 'components/common'
import {
  addReleaseToCsv,
  addTrackToCsv,
  getAlbumTracks,
  getLocalReleasesFetchJob,
  listCsvReleases,
  listLocalReleases,
  startLocalReleasesFetch,
} from 'backendApi'

/**
 * Releases screen
 */
function Releases() {
  const [releases, setReleases] = useState([])
  const [csvReleaseIds, setCsvReleaseIds] = useState(new Set())
  const [query, setQuery] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [excludeVariousArtists, setExcludeVariousArtists] = useState(true)
  const [excludeRemixes, setExcludeRemixes] = useState(true)
  const [excludeDuplicates, setExcludeDuplicates] = useState(true)
  const [loading, setLoading] = useState(true)
  const [fetchingSpotify, setFetchingSpotify] = useState(false)
  const [fetchProgress, setFetchProgress] = useState(null)
  const [addingReleaseId, setAddingReleaseId] = useState('')
  const [expandedAlbums, setExpandedAlbums] = useState({})
  const [albumTracks, setAlbumTracks] = useState({})
  const [loadingAlbumId, setLoadingAlbumId] = useState('')
  const [error, setError] = useState('')
  const [infoMessage, setInfoMessage] = useState('')
  const [fetchDayFilter, setFetchDayFilter] = useState('all')
  const [collapsedFetchDays, setCollapsedFetchDays] = useState({})

  const loadData = async () => {
    setLoading(true)
    setError('')
    try {
      const [localReleases, csvReleases] = await Promise.all([listLocalReleases(), listCsvReleases()])
      setReleases(localReleases)
      setCsvReleaseIds(new Set(csvReleases.map((release) => release.id)))
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const end = new Date()
    const start = new Date()
    start.setDate(end.getDate() - 30)
    setEndDate(end.toISOString().slice(0, 10))
    setStartDate(start.toISOString().slice(0, 10))
    loadData()
  }, [])

  const filteredReleases = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    const seen = new Set()

    return releases.filter((release) => {
      const releaseName = String(release.name || '')
      const artistName = String(release.artist_name || '')
      const normalizedReleaseName = releaseName.toLowerCase().trim()
      const normalizedArtistName = artistName.toLowerCase().trim()

      if (
        normalizedQuery &&
        !normalizedReleaseName.includes(normalizedQuery) &&
        !normalizedArtistName.includes(normalizedQuery)
      ) {
        return false
      }

      if (excludeVariousArtists && normalizedArtistName === 'various artists') return false
      if (excludeRemixes && /remix/i.test(releaseName)) return false

      if (excludeDuplicates) {
        const duplicateKey = `${normalizedReleaseName}::${normalizedArtistName}::${release.release_date}`
        if (seen.has(duplicateKey)) return false
        seen.add(duplicateKey)
      }

      return true
    })
  }, [excludeDuplicates, excludeRemixes, excludeVariousArtists, query, releases])

  const fetchedDayOptions = useMemo(() => {
    const unique = new Set(
      releases.map((release) => {
        const fetchedAt = String(release.fetched_at || '')
        return fetchedAt ? fetchedAt.slice(0, 10) : 'sem-fetch-day'
      })
    )
    return Array.from(unique).sort((a, b) => (a < b ? 1 : -1))
  }, [releases])

  const sortedReleases = useMemo(
    () =>
      [...filteredReleases]
        .filter((release) => {
          if (fetchDayFilter === 'all') return true
          const fetchedAt = String(release.fetched_at || '')
          const fetchedDay = fetchedAt ? fetchedAt.slice(0, 10) : 'sem-fetch-day'
          return fetchedDay === fetchDayFilter
        })
        .sort((a, b) => String(b.release_date || '').localeCompare(String(a.release_date || ''))),
    [fetchDayFilter, filteredReleases]
  )

  const groupedByFetchedDay = useMemo(() => {
    const groups = {}
    for (const release of sortedReleases) {
      const fetchedAt = String(release.fetched_at || '')
      const key = fetchedAt ? fetchedAt.slice(0, 10) : 'sem-fetch-day'
      if (!groups[key]) groups[key] = []
      groups[key].push(release)
    }
    return Object.entries(groups).sort((a, b) => (a[0] < b[0] ? 1 : -1))
  }, [sortedReleases])

  const toggleFetchDay = (dayKey) => {
    setCollapsedFetchDays((previous) => ({ ...previous, [dayKey]: !previous[dayKey] }))
  }

  const onAddToCsv = async (release) => {
    setError('')
    setInfoMessage('')
    setAddingReleaseId(release.id)
    try {
      await addReleaseToCsv(release.id)
      setCsvReleaseIds((previous) => new Set([...previous, release.id]))
      setInfoMessage(`"${release.name}" adicionada na playlist.`)
    } catch (err) {
      setError(err.message)
    } finally {
      setAddingReleaseId('')
    }
  }

  const onToggleAlbum = async (release) => {
    const isExpanded = Boolean(expandedAlbums[release.id])
    if (isExpanded) {
      setExpandedAlbums((previous) => ({ ...previous, [release.id]: false }))
      return
    }
    setExpandedAlbums((previous) => ({ ...previous, [release.id]: true }))
    if (albumTracks[release.id]) return

    setLoadingAlbumId(release.id)
    try {
      const tracks = await getAlbumTracks(release.id)
      setAlbumTracks((previous) => ({ ...previous, [release.id]: tracks }))
    } catch (err) {
      setError(err.message)
    } finally {
      setLoadingAlbumId('')
    }
  }

  const onAddTrackToCsv = async (track) => {
    setError('')
    setInfoMessage('')
    setAddingReleaseId(track.id)
    try {
      await addTrackToCsv({
        id: track.id,
        name: track.name,
        artist_name: track.artist_name,
        album_type: 'single',
        spotify_url: track.spotify_url || null,
      })
      setCsvReleaseIds((previous) => new Set([...previous, track.id]))
      setInfoMessage(`"${track.name}" adicionada na playlist.`)
    } catch (err) {
      setError(err.message)
    } finally {
      setAddingReleaseId('')
    }
  }

  const onFetchFromSpotify = async () => {
    setError('')
    setInfoMessage('')
    setFetchingSpotify(true)
    setFetchProgress(null)
    try {
      const { job_id: jobId } = await startLocalReleasesFetch({
        period: 'custom',
        startDate,
        endDate,
      })
      let completed = false

      while (!completed) {
        // eslint-disable-next-line no-await-in-loop
        const job = await getLocalReleasesFetchJob(jobId)
        setFetchProgress(job)
        if (job.status === 'completed') {
          completed = true
          // eslint-disable-next-line no-await-in-loop
          await loadData()
          setInfoMessage(
            `Fetch concluido: ${job.fetched_releases} releases encontradas, ${job.stored_releases} guardadas.`
          )
          break
        }
        if (job.status === 'failed') {
          throw new Error(job.error || 'Falha no fetch de releases')
        }
        // eslint-disable-next-line no-await-in-loop
        await new Promise((resolve) => setTimeout(resolve, 1200))
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setFetchingSpotify(false)
    }
  }

  return (
    <VerticalLayout>
      <Header title="Releases locais">
        <div className="Header__right">
          <ButtonLink to="/artists" title="Gerir artistas" icon="fas fa-users" compact>
            Artistas
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
          <div className="LocalPanel LocalPanel--toolbar mb-4">
            <div className="LocalTopRow">
              <div className="field LocalTopRow__date">
                <label className="label has-text-light">Inicio</label>
                <Input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
              </div>
              <div className="field LocalTopRow__date">
                <label className="label has-text-light">Fim</label>
                <Input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
              </div>
              <div className="field LocalTopRow__search">
                <label className="label has-text-light">Pesquisar</label>
                <Input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Nome da release ou artista"
                />
              </div>
              <div className="LocalTopRow__actions">
                <Button onClick={onFetchFromSpotify} primary disabled={fetchingSpotify || !startDate || !endDate}>
                  {fetchingSpotify ? 'A puxar...' : 'Puxar releases'}
                </Button>
                <Button onClick={loadData} primary disabled={loading}>
                  {loading ? 'A atualizar...' : 'Atualizar'}
                </Button>
              </div>
            </div>
        <div className="mb-4 LocalFiltersRow">
          <label className="checkbox LocalFilterOption">
            <input
              type="checkbox"
              checked={excludeVariousArtists}
              onChange={(event) => setExcludeVariousArtists(event.target.checked)}
            />{' '}
            Excluir Various Artists
          </label>
          <label className="checkbox LocalFilterOption">
            <input
              type="checkbox"
              checked={excludeRemixes}
              onChange={(event) => setExcludeRemixes(event.target.checked)}
            />{' '}
            Excluir remixes
          </label>
          <label className="checkbox LocalFilterOption">
            <input
              type="checkbox"
              checked={excludeDuplicates}
              onChange={(event) => setExcludeDuplicates(event.target.checked)}
            />{' '}
            Excluir duplicados
          </label>
          <div className="LocalFetchDayFilter">
            <span className="LocalFetchDayFilter__label">Dia do fetch</span>
            <div className="select is-small LocalFetchDayFilter__select">
              <select value={fetchDayFilter} onChange={(event) => setFetchDayFilter(event.target.value)}>
                <option value="all">Todos</option>
                {fetchedDayOptions.map((day) => (
                  <option key={day} value={day}>
                    {day === 'sem-fetch-day' ? 'Sem dia de fetch' : day}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
        </div>
        {error && <p className="has-text-danger">{error}</p>}
        {infoMessage && <p className="has-text-success">{infoMessage}</p>}
        {fetchingSpotify && fetchProgress && (
          <p className="has-text-info">
            Fetch em progresso: {fetchProgress.progress}% ({fetchProgress.processed_artists}/
            {fetchProgress.total_artists} artistas), {fetchProgress.fetched_releases} releases encontradas.
          </p>
        )}
        {loading && <p className="has-text-grey">A carregar releases...</p>}
        {!loading && !filteredReleases.length && (
          <p className="has-text-grey">Sem releases guardadas. Faz fetch na pagina de artistas.</p>
        )}

        {!loading && groupedByFetchedDay.length > 0 && (
          <div className="LocalReleaseGroups">
            {groupedByFetchedDay.map(([fetchDay, dayReleases]) => (
              <div className="mb-4" key={fetchDay}>
                <div className="LocalFetchDayHeader">
                  <Button className="LocalActionButton" onClick={() => toggleFetchDay(fetchDay)}>
                    {collapsedFetchDays[fetchDay] ? 'Expand' : 'Collapse'}
                  </Button>
                  <p className="LocalFetchDayTitle">
                    Fetch: {fetchDay === 'sem-fetch-day' ? 'Sem dia de fetch' : fetchDay} ({dayReleases.length})
                  </p>
                </div>
                {!collapsedFetchDays[fetchDay] && (
                  <div className="columns is-multiline">
                    {dayReleases.map((release) => (
                      <div className="column is-half-tablet is-one-third-desktop is-one-quarter-widescreen" key={release.id}>
                        <article className="box LocalReleaseCard">
                    <p className="LocalReleaseDateBadge">{release.release_date || 'Sem data'}</p>
                    <div className="media">
                      <div className="media-left">
                        <figure className="image is-64x64 LocalReleaseCover">
                          {release.image_url ? (
                            <img src={release.image_url} alt={release.name} />
                          ) : (
                            <div className="LocalReleaseCover__placeholder" />
                          )}
                        </figure>
                      </div>
                      <div className="media-content">
                        <p className="has-text-weight-semibold LocalReleaseTitle">{release.name}</p>
                        <p className="LocalReleaseArtist">{release.artist_name}</p>
                        {Array.isArray(release.matched_artists) && release.matched_artists.length > 0 && (
                          <p
                            className="LocalReleaseReason"
                            style={{ fontWeight: release.has_non_primary_match ? 700 : 400 }}
                          >
                            Incluida por: {release.matched_artists.join(', ')}
                            {release.has_non_primary_match ? ' (participacao, nao principal)' : ''}
                          </p>
                        )}
                        <p className="LocalReleaseType">{release.album_type}</p>
                      </div>
                    </div>
                    <div className="mt-3 LocalReleaseActionsRow">
                      <div className="LocalReleaseActionsLeft">
                        {release.spotify_url && (
                          <a href={release.spotify_url} target="_blank" rel="noreferrer" className="LocalSpotifyLinkButton">
                            Abrir no Spotify
                          </a>
                        )}
                        {(release.album_type === 'album' || release.album_type === 'compilation') && (
                          <Button
                            onClick={() => onToggleAlbum(release)}
                            disabled={loadingAlbumId === release.id}
                            className="LocalActionButton"
                          >
                            {expandedAlbums[release.id] ? 'Collapse' : 'Expand'}
                          </Button>
                        )}
                      </div>
                      <Button
                        onClick={() => onAddToCsv(release)}
                        disabled={csvReleaseIds.has(release.id) || addingReleaseId === release.id}
                        className="LocalActionButton LocalActionButton--primary"
                      >
                        {csvReleaseIds.has(release.id)
                          ? 'No CSV'
                          : addingReleaseId === release.id
                            ? 'A adicionar...'
                            : 'Adicionar à playlist'}
                      </Button>
                    </div>
                    {expandedAlbums[release.id] && (
                      <div className="mt-3 LocalTrackList">
                        {loadingAlbumId === release.id && (
                          <p className="is-size-7 has-text-grey">A carregar faixas...</p>
                        )}
                        {(albumTracks[release.id] || []).map((track) => (
                          <div
                            key={track.id}
                            className="is-flex is-justify-content-space-between is-align-items-center mb-1"
                          >
                            <span className="LocalTrackRow__title">
                              {track.name} - {track.artist_name}
                            </span>
                            <Button
                              onClick={() => onAddTrackToCsv(track)}
                              disabled={csvReleaseIds.has(track.id) || addingReleaseId === track.id}
                              className="LocalActionButton"
                            >
                              {csvReleaseIds.has(track.id)
                                ? 'No CSV'
                                : addingReleaseId === track.id
                                  ? 'A adicionar...'
                                  : 'Adicionar à playlist'}
                            </Button>
                          </div>
                        ))}
                      </div>
                    )}
                        </article>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
        </div>
      </Content>
    </VerticalLayout>
  )
}

export default Releases
