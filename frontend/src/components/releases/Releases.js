import { useEffect, useMemo, useState } from 'react'
import { Button, Content, Header, HeaderNav, Input, VerticalLayout } from 'components/common'
import {
  addReleaseToCsv,
  addTrackToCsv,
  deleteLocalReleasesByFetchedDay,
  getLocalReleasesFetchJob,
  getSettings,
  getTidalAlbumTracks,
  getTidalDeviceStatus,
  getTidalSession,
  listCsvReleases,
  listLocalReleases,
  searchTidalTracks,
  startLocalReleasesFetch,
  startTidalDeviceLogin,
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
  const [fetchingTidal, setFetchingTidal] = useState(false)
  const [fetchProgress, setFetchProgress] = useState(null)
  const [addingReleaseId, setAddingReleaseId] = useState('')
  const [expandedAlbums, setExpandedAlbums] = useState({})
  const [albumTracks, setAlbumTracks] = useState({})
  const [loadingAlbumId, setLoadingAlbumId] = useState('')
  const [error, setError] = useState('')
  const [infoMessage, setInfoMessage] = useState('')
  const [fetchDayFilter, setFetchDayFilter] = useState('all')
  const [collapsedFetchDays, setCollapsedFetchDays] = useState({})
  const [trackSearchQuery, setTrackSearchQuery] = useState('')
  const [trackSearchResults, setTrackSearchResults] = useState([])
  const [trackSearchLoading, setTrackSearchLoading] = useState(false)
  const [tidalLoginOpen, setTidalLoginOpen] = useState(false)
  const [tidalLoginPayload, setTidalLoginPayload] = useState(null)
  const [tidalLoginStatus, setTidalLoginStatus] = useState('')
  const [filtersDropdownOpen, setFiltersDropdownOpen] = useState(false)
  const [deletingFetchDay, setDeletingFetchDay] = useState('')

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
    async function init() {
      const today = new Date().toISOString().slice(0, 10)
      let start = ''
      try {
        const settings = await getSettings()
        const saved = String(settings.last_releases_fetch_end_date || '').trim()
        if (saved && /^\d{4}-\d{2}-\d{2}$/.test(saved)) {
          start = saved > today ? today : saved
        }
      } catch {
        /* fallback below */
      }
      if (!start) {
        const d = new Date()
        d.setDate(d.getDate() - 30)
        start = d.toISOString().slice(0, 10)
      }
      setEndDate(today)
      setStartDate(start)
      loadData()
    }
    init()
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

  const listFiltersActiveCount = useMemo(() => {
    let n = 0
    if (query.trim()) n += 1
    if (fetchDayFilter !== 'all') n += 1
    if (!excludeVariousArtists) n += 1
    if (!excludeRemixes) n += 1
    if (!excludeDuplicates) n += 1
    return n
  }, [query, fetchDayFilter, excludeVariousArtists, excludeRemixes, excludeDuplicates])

  useEffect(() => {
    if (!filtersDropdownOpen) return
    const onDocDown = (event) => {
      const el = event.target
      if (el instanceof Node && !el.closest?.('.LocalReleasesFilterDropdown')) {
        setFiltersDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', onDocDown)
    return () => document.removeEventListener('mousedown', onDocDown)
  }, [filtersDropdownOpen])

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

  const onDeleteFetchDay = async (fetchDay, count) => {
    const label = fetchDay === 'sem-fetch-day' ? 'Sem dia de fetch' : fetchDay
    const confirmed = window.confirm(
      `Apagar ${count} release(s) do batch "${label}"? Esta acao nao pode ser desfeita.`
    )
    if (!confirmed) return

    setError('')
    setInfoMessage('')
    setDeletingFetchDay(fetchDay)
    try {
      const result = await deleteLocalReleasesByFetchedDay(fetchDay)
      setInfoMessage(`Apagadas ${result.deleted} release(s) de ${label}.`)
      if (fetchDayFilter === fetchDay) setFetchDayFilter('all')
      await loadData()
    } catch (err) {
      setError(err.message)
    } finally {
      setDeletingFetchDay('')
    }
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
      const rawId = String(release.id ?? '').trim()
      const fromUrl = String(release.tidal_url || '').match(/\/album\/(\d+)/i)
      const tidalAlbumId = /^\d+$/.test(rawId) ? rawId : fromUrl?.[1] || ''
      if (!tidalAlbumId) {
        setAlbumTracks((previous) => ({ ...previous, [release.id]: [] }))
        setInfoMessage(
          'Este release não tem ID Tidal numérico (provavelmente registo antigo Spotify). Faz um fetch Tidal novo ou apaga o batch antigo.'
        )
        return
      }
      const tracks = await getTidalAlbumTracks(tidalAlbumId)
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
        tidal_url: track.tidal_url || null,
      })
      setCsvReleaseIds((previous) => new Set([...previous, track.id]))
      setInfoMessage(`"${track.name}" adicionada na playlist.`)
    } catch (err) {
      setError(err.message)
    } finally {
      setAddingReleaseId('')
    }
  }

  const onSearchTidalTracks = async () => {
    const q = trackSearchQuery.trim()
    if (q.length < 2) {
      setTrackSearchResults([])
      return
    }
    setTrackSearchLoading(true)
    setError('')
    try {
      await ensureTidalLogin()
      const rows = await searchTidalTracks(q, 15)
      setTrackSearchResults(rows)
    } catch (err) {
      setError(err.message)
      setTrackSearchResults([])
    } finally {
      setTrackSearchLoading(false)
    }
  }

  const ensureTidalLogin = async () => {
    const session = await getTidalSession()
    if (session?.logged_in === true) return true

    setTidalLoginOpen(true)
    setTidalLoginPayload(null)
    setTidalLoginStatus('A iniciar login Tidal…')
    // Deixa o React pintar o modal antes do await longo
    await new Promise((r) => setTimeout(r, 50))

    const start = await startTidalDeviceLogin()
    if (start.status === 'already_logged_in') {
      setTidalLoginOpen(false)
      return true
    }
    if (start.status === 'failed') {
      const msg = start.error || 'Falha ao iniciar device login'
      setTidalLoginStatus(msg)
      throw new Error(msg)
    }
    if (start.status === 'busy') {
      setTidalLoginStatus(start.message || 'Login já em curso; a aguardar…')
    }
    if (start.verification_uri_complete) {
      setTidalLoginPayload({
        link: start.verification_uri_complete,
        userCode: start.user_code,
        expiresIn: start.expires_in,
      })
      setTidalLoginStatus('Abre o link, faz login no Tidal e autoriza. Esta página aguarda.')
    }

    const deadline = Date.now() + 20 * 60 * 1000
    let idleStreak = 0

    for (;;) {
      if (Date.now() > deadline) {
        throw new Error('Tempo limite do login Tidal (20 min). Tenta de novo.')
      }
      // eslint-disable-next-line no-await-in-loop
      await new Promise((r) => setTimeout(r, 1500))
      // eslint-disable-next-line no-await-in-loop
      const st = await getTidalDeviceStatus()
      if (st.verification_uri_complete) {
        setTidalLoginPayload((prev) => ({
          link: st.verification_uri_complete,
          userCode: st.user_code ?? prev?.userCode,
          expiresIn: st.expires_in ?? prev?.expiresIn,
        }))
      }
      if (st.status === 'logged_in') {
        setTidalLoginOpen(false)
        setTidalLoginPayload(null)
        setTidalLoginStatus('')
        return true
      }
      if (st.status === 'failed') {
        const msg = st.error || 'Login Tidal falhou ou expirou'
        setTidalLoginStatus(msg)
        throw new Error(msg)
      }
      if (st.status === 'idle') {
        idleStreak += 1
        if (idleStreak >= 6) {
          throw new Error(
            'O servidor perdeu o estado do login Tidal (idle). Usa um único processo uvicorn (sem --workers > 1) ou recarrega a página.'
          )
        }
        continue
      }
      idleStreak = 0
    }
  }

  const onFetchTidalReleases = async () => {
    setError('')
    setInfoMessage('')
    setFetchingTidal(true)
    setFetchProgress(null)
    try {
      await ensureTidalLogin()
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
          try {
            const settings = await getSettings()
            const next = String(settings.last_releases_fetch_end_date || '').trim()
            if (next && /^\d{4}-\d{2}-\d{2}$/.test(next)) {
              const today = new Date().toISOString().slice(0, 10)
              setStartDate(next > today ? today : next)
              setEndDate(today)
            }
          } catch {
            /* ignore */
          }
          if ((job.total_artists ?? 0) === 0) {
            setInfoMessage(
              'Fetch concluido: nenhum artista com ID Tidal definido. Em Gerir Artistas, preenche e guarda o campo «ID Tidal» para cada artista que queres sincronizar.'
            )
          } else {
            setInfoMessage(
              `Fetch concluido: ${job.fetched_releases} releases encontradas, ${job.stored_releases} guardadas.`
            )
          }
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
      setTidalLoginOpen(false)
    } finally {
      setFetchingTidal(false)
    }
  }

  return (
    <VerticalLayout>
      <Header>
        <HeaderNav />
      </Header>
      <Content>
        <div className="LocalPage LocalPage--full">
          <div className="LocalPanel LocalPanel--toolbar LocalReleasesToolbar mb-4">
            <div className="LocalTopRow LocalReleasesToolbar__row">
              <div className="LocalTopRow LocalReleasesToolbar__main">
                <div className="field LocalTopRow__date">
                  <label className="label has-text-light">Início</label>
                  <Input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
                </div>
                <div className="field LocalTopRow__date">
                  <label className="label has-text-light">Fim</label>
                  <Input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
                </div>
                <div className="field LocalReleasesToolbar__tidal">
                  <label className="label has-text-light">Tidal — faixa</label>
                  <Input
                    value={trackSearchQuery}
                    onChange={(event) => setTrackSearchQuery(event.target.value)}
                    placeholder="Artista ou faixa"
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') onSearchTidalTracks()
                    }}
                  />
                </div>
                <Button onClick={onSearchTidalTracks} primary disabled={trackSearchLoading}>
                  {trackSearchLoading ? '…' : 'Procurar'}
                </Button>
              </div>
              <div className="LocalReleasesToolbar__tail">
                <div className="LocalTopRow__actions">
                  <Button onClick={onFetchTidalReleases} primary disabled={fetchingTidal || !startDate || !endDate}>
                    {fetchingTidal ? 'A puxar...' : 'Puxar releases'}
                  </Button>
                  <Button onClick={loadData} primary disabled={loading}>
                    {loading ? 'A atualizar...' : 'Atualizar'}
                  </Button>
                </div>
                <div
                  className={`dropdown LocalReleasesFilterDropdown ${filtersDropdownOpen ? 'is-active' : ''}`}
                  onKeyDown={(event) => {
                    if (event.key === 'Escape') setFiltersDropdownOpen(false)
                  }}
                >
                  <div className="dropdown-trigger">
                    <Button
                      type="button"
                      className="LocalReleasesFilterDropdown__trigger"
                      aria-haspopup="true"
                      aria-expanded={filtersDropdownOpen}
                      onClick={() => setFiltersDropdownOpen((open) => !open)}
                    >
                      Filtros da lista
                      {listFiltersActiveCount > 0 ? (
                        <span className="LocalReleasesFilterDropdown__badge">{listFiltersActiveCount}</span>
                      ) : null}
                    </Button>
                  </div>
                  <div className="dropdown-menu is-right LocalReleasesFilterDropdown__menu" role="menu">
                    <div className="dropdown-content">
                      <div className="field mb-3">
                        <label className="label has-text-light is-size-7">Artista ou release</label>
                        <Input
                          value={query}
                          onChange={(event) => setQuery(event.target.value)}
                          placeholder="Filtrar na lista guardada"
                        />
                      </div>
                      <div className="field mb-3">
                        <label className="label has-text-light is-size-7">Dia do fetch</label>
                        <div className="select is-fullwidth LocalReleasesFilterDropdown__select">
                          <select value={fetchDayFilter} onChange={(event) => setFetchDayFilter(event.target.value)}>
                            <option value="all">Todos os dias</option>
                            {fetchedDayOptions.map((day) => (
                              <option key={day} value={day}>
                                {day === 'sem-fetch-day' ? 'Sem dia de fetch' : day}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>
                      <p className="is-size-7 has-text-grey mb-2">Excluir da lista</p>
                      <label className="checkbox has-text-light is-block mb-2">
                        <input
                          type="checkbox"
                          checked={excludeVariousArtists}
                          onChange={(event) => setExcludeVariousArtists(event.target.checked)}
                        />{' '}
                        Various Artists
                      </label>
                      <label className="checkbox has-text-light is-block mb-2">
                        <input
                          type="checkbox"
                          checked={excludeRemixes}
                          onChange={(event) => setExcludeRemixes(event.target.checked)}
                        />{' '}
                        Remixes
                      </label>
                      <label className="checkbox has-text-light is-block">
                        <input
                          type="checkbox"
                          checked={excludeDuplicates}
                          onChange={(event) => setExcludeDuplicates(event.target.checked)}
                        />{' '}
                        Duplicados (mesmo título/artista/data)
                      </label>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            {trackSearchResults.length > 0 && (
              <div className="LocalTrackSearchResults LocalReleasesToolbar__results">
                {trackSearchResults.map((track) => (
                  <div className="LocalTrackSearchItem" key={track.id}>
                    <div className="LocalTrackSearchItem__meta">
                      <div className="LocalTrackSearchItem__title">{track.name}</div>
                      <div className="LocalTrackSearchItem__artist">{track.artist_name}</div>
                    </div>
                    <div className="LocalTrackSearchItem__actions">
                      <Button
                        className="LocalActionButton"
                        onClick={() => onAddTrackToCsv(track)}
                        disabled={csvReleaseIds.has(track.id) || addingReleaseId === track.id}
                      >
                        {csvReleaseIds.has(track.id)
                          ? 'No CSV'
                          : addingReleaseId === track.id
                            ? 'A adicionar...'
                            : 'Adicionar à playlist'}
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        {tidalLoginOpen && (
          <div className="modal is-active" style={{ zIndex: 10050 }}>
            <div className="modal-background" />
            <div className="modal-card has-background-dark" style={{ zIndex: 10051 }}>
              <header className="modal-card-head has-background-dark">
                <p className="modal-card-title has-text-light">Login Tidal</p>
              </header>
              <section className="modal-card-body has-text-light">
                <p className="mb-3">{tidalLoginStatus}</p>
                {tidalLoginPayload?.link && (
                  <>
                    <p className="is-size-7 has-text-grey mb-2">Código: {tidalLoginPayload.userCode}</p>
                    <a
                      href={tidalLoginPayload.link}
                      target="_blank"
                      rel="noreferrer"
                      className="button is-link is-fullwidth mb-2"
                    >
                      Abrir página de login Tidal
                    </a>
                    <p className="is-size-7 has-text-grey">
                      O servidor aguarda até concluíres o login (como no script de teste). Não fechas esta janela
                      até aparecer &quot;Fetch&quot; ou erro.
                    </p>
                  </>
                )}
              </section>
            </div>
          </div>
        )}
        {error && <p className="has-text-danger">{error}</p>}
        {infoMessage && <p className="has-text-success">{infoMessage}</p>}
        {fetchingTidal && fetchProgress && (
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
                  <div className="LocalFetchDayHeader__left">
                    <Button className="LocalActionButton" onClick={() => toggleFetchDay(fetchDay)}>
                      {collapsedFetchDays[fetchDay] ? 'Expand' : 'Collapse'}
                    </Button>
                    <p className="LocalFetchDayTitle">
                      Fetch: {fetchDay === 'sem-fetch-day' ? 'Sem dia de fetch' : fetchDay} (
                      {dayReleases.length})
                    </p>
                  </div>
                  <Button
                    danger
                    className="LocalActionButton"
                    disabled={deletingFetchDay === fetchDay}
                    onClick={() => onDeleteFetchDay(fetchDay, dayReleases.length)}
                  >
                    {deletingFetchDay === fetchDay ? 'A apagar...' : 'Delete'}
                  </Button>
                </div>
                {!collapsedFetchDays[fetchDay] && (
                  <div className="columns is-multiline is-mobile LocalReleaseGrid">
                    {dayReleases.map((release) => {
                      const canExpand = ['album', 'compilation', 'single'].includes(release.album_type)
                      const isExpanded = Boolean(expandedAlbums[release.id])
                      const inPlaylist = csvReleaseIds.has(release.id)
                      const adding = addingReleaseId === release.id
                      const showRoleBadge =
                        Array.isArray(release.matched_artists) && release.matched_artists.length > 0
                      const isPrincipal = showRoleBadge && !release.has_non_primary_match

                      return (
                        <div
                          className="column is-full-mobile is-one-quarter-tablet is-one-fifth-desktop is-2-widescreen"
                          key={release.id}
                        >
                          <article className="box LocalReleaseCard">
                            <div className="LocalReleaseCard__row">
                              <div className="LocalReleaseCard__main">
                                <div className="LocalReleaseCard__meta">
                                  <span className="LocalReleaseDateBadge">
                                    {release.release_date || 'Sem data'}
                                  </span>
                                  <span className="LocalReleaseType">
                                    {release.album_type || 'release'}
                                  </span>
                                  {showRoleBadge && (
                                    <span
                                      className={
                                        isPrincipal
                                          ? 'LocalReleaseRoleBadge'
                                          : 'LocalReleaseRoleBadge LocalReleaseRoleBadge--feature'
                                      }
                                      title={
                                        isPrincipal
                                          ? `Incluida por: ${release.matched_artists.join(', ')}`
                                          : `Incluida por: ${release.matched_artists.join(', ')} (participacao)`
                                      }
                                    >
                                      {isPrincipal ? 'principal' : 'participacao'}
                                    </span>
                                  )}
                                </div>
                                <div className="LocalReleaseCard__info">
                                  <figure className="LocalReleaseCover">
                                    {release.image_url ? (
                                      <img src={release.image_url} alt={release.name} />
                                    ) : (
                                      <div className="LocalReleaseCover__placeholder" />
                                    )}
                                  </figure>
                                  <div className="LocalReleaseCard__text">
                                    <p className="LocalReleaseTitle" title={release.name}>
                                      {release.name}
                                    </p>
                                    <p className="LocalReleaseArtist" title={release.artist_name}>
                                      {release.artist_name}
                                    </p>
                                  </div>
                                </div>
                              </div>
                              <div className="LocalReleaseCard__actions">
                                {release.tidal_url ? (
                                  <a
                                    href={release.tidal_url}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="LocalReleaseIconBtn"
                                    title="Abrir no Tidal"
                                  >
                                    <i className="fas fa-up-right-from-square" aria-hidden="true" />
                                  </a>
                                ) : (
                                  <span className="LocalReleaseIconBtn LocalReleaseIconBtn--ghost" aria-hidden="true" />
                                )}
                                <button
                                  type="button"
                                  className="LocalReleaseIconBtn"
                                  title={
                                    inPlaylist
                                      ? 'Ja na playlist'
                                      : adding
                                        ? 'A adicionar...'
                                        : 'Adicionar a playlist'
                                  }
                                  disabled={inPlaylist || adding}
                                  onClick={() => onAddToCsv(release)}
                                >
                                  <i
                                    className={inPlaylist ? 'fas fa-check' : 'fas fa-list'}
                                    aria-hidden="true"
                                  />
                                </button>
                                {canExpand ? (
                                  <button
                                    type="button"
                                    className="LocalReleaseIconBtn"
                                    title={isExpanded ? 'Fechar faixas' : 'Ver faixas'}
                                    disabled={loadingAlbumId === release.id}
                                    onClick={() => onToggleAlbum(release)}
                                  >
                                    <i
                                      className={isExpanded ? 'fas fa-compress' : 'fas fa-expand'}
                                      aria-hidden="true"
                                    />
                                  </button>
                                ) : (
                                  <span className="LocalReleaseIconBtn LocalReleaseIconBtn--ghost" aria-hidden="true" />
                                )}
                              </div>
                            </div>
                            {isExpanded && (
                              <div className="LocalTrackList">
                                {loadingAlbumId === release.id && (
                                  <p className="is-size-7 has-text-grey">A carregar faixas...</p>
                                )}
                                {(albumTracks[release.id] || []).map((track) => (
                                  <div key={track.id} className="LocalTrackRow">
                                    <span className="LocalTrackRow__title">
                                      {track.name} - {track.artist_name}
                                    </span>
                                    <button
                                      type="button"
                                      className="LocalReleaseIconBtn LocalReleaseIconBtn--sm"
                                      title={
                                        csvReleaseIds.has(track.id)
                                          ? 'Ja na playlist'
                                          : addingReleaseId === track.id
                                            ? 'A adicionar...'
                                            : 'Adicionar a playlist'
                                      }
                                      disabled={
                                        csvReleaseIds.has(track.id) || addingReleaseId === track.id
                                      }
                                      onClick={() => onAddTrackToCsv(track)}
                                    >
                                      <i
                                        className={
                                          csvReleaseIds.has(track.id) ? 'fas fa-check' : 'fas fa-list'
                                        }
                                        aria-hidden="true"
                                      />
                                    </button>
                                  </div>
                                ))}
                              </div>
                            )}
                          </article>
                        </div>
                      )
                    })}
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
