import { useEffect, useMemo, useState } from 'react'
import { Button, Input, VerticalLayout, Header, Content, ButtonLink } from 'components/common'
import {
  createArtist,
  deleteArtist,
  getTidalSession,
  listArtists,
  patchArtistTidalId,
  refreshArtists,
  searchTidalArtists,
} from 'backendApi'

/**
 * @typedef {object} StoredArtist
 * @property {string|number} id
 * @property {string} name
 * @property {string} [image_url]
 * @property {string} [spotify_id]
 * @property {string|number} [tidal_id]
 */

/**
 * @typedef {object} TidalSearchArtist
 * @property {string|number} id
 * @property {string} name
 * @property {string} [image_url]
 */

/** @param {unknown} err */
function formatErrorMessage(err) {
  return err instanceof Error ? err.message : String(err)
}

function ManageArtists() {
  const [artists, setArtists] = useState(/** @type {StoredArtist[]} */ ([]))
  const [query, setQuery] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState(/** @type {TidalSearchArtist[]} */ ([]))
  const [searchLoading, setSearchLoading] = useState(false)
  const [refreshingArtists, setRefreshingArtists] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [infoMessage, setInfoMessage] = useState('')
  const [tidalDrafts, setTidalDrafts] = useState(/** @type {Record<string, string>} */ ({}))
  const [savingTidalId, setSavingTidalId] = useState('')

  const loadArtists = async () => {
    setLoading(true)
    setError('')
    try {
      const data = /** @type {StoredArtist[]} */ (await listArtists())
      setArtists(data)
      /** @type {Record<string, string>} */
      const nextDrafts = {}
      for (const a of data) {
        const sid = a.spotify_id != null ? String(a.spotify_id).trim() : ''
        const idStr = String(a.id ?? '')
        const legacyTidalInId = sid && /^\d+$/.test(idStr)
        const tidal =
          a.tidal_id != null && a.tidal_id !== undefined && String(a.tidal_id).trim()
            ? String(a.tidal_id).trim()
            : legacyTidalInId
              ? idStr
              : ''
        nextDrafts[String(a.id)] = tidal
      }
      setTidalDrafts(nextDrafts)
    } catch (err) {
      setError(formatErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadArtists()
  }, [])

  /** @param {string|number} artistId */
  const onDelete = async (artistId) => {
    setError('')
    try {
      await deleteArtist(artistId)
      await loadArtists()
    } catch (err) {
      setError(formatErrorMessage(err))
    }
  }

  /** @param {import('react').MouseEvent | import('react').FormEvent | undefined} event */
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
      const session = await getTidalSession()
      if (!session?.logged_in) {
        setError('Inicia sessão Tidal na página Releases (login no popup) antes de pesquisar artistas.')
        setSearchResults([])
        return
      }
      const data = /** @type {TidalSearchArtist[]} */ (await searchTidalArtists(searchQuery.trim()))
      setSearchResults(data)
    } catch (err) {
      setError(formatErrorMessage(err))
    } finally {
      setSearchLoading(false)
    }
  }

  /** @param {TidalSearchArtist} artist */
  const onAddFromSearch = async (artist) => {
    setError('')
    try {
      await createArtist({
        id: artist.id,
        name: artist.name,
        image_url: artist.image_url || null,
        spotify_id: '',
      })
      await loadArtists()
    } catch (err) {
      setError(formatErrorMessage(err))
    }
  }

  /** @param {string|number} artistId */
  const onSaveTidalId = async (artistId) => {
    setError('')
    setInfoMessage('')
    setSavingTidalId(String(artistId))
    try {
      await patchArtistTidalId(artistId, tidalDrafts[String(artistId)])
      setInfoMessage('ID Tidal guardado.')
      await loadArtists()
    } catch (err) {
      setError(formatErrorMessage(err))
    } finally {
      setSavingTidalId('')
    }
  }

  const onRefreshArtistsInfo = async () => {
    setError('')
    setInfoMessage('')
    setRefreshingArtists(true)
    try {
      const result = await refreshArtists(true)
      await loadArtists()
      const extra = result.message ? ` ${result.message}` : ''
      setInfoMessage(`Atualizacao concluida: ${result.updated}/${result.total} artistas atualizados.${extra}`)
    } catch (err) {
      setError(formatErrorMessage(err))
    } finally {
      setRefreshingArtists(false)
    }
  }

  /** @type {import('react').ChangeEventHandler<HTMLInputElement>} */
  const onSearchQueryChange = (event) => setSearchQuery(event.target.value)

  /** @type {import('react').ChangeEventHandler<HTMLInputElement>} */
  const onFilterQueryChange = (event) => setQuery(event.target.value)

  /** @param {string|number} artistId */
  const onTidalDraftInputChange = (artistId) => {
    /** @type {import('react').ChangeEventHandler<HTMLInputElement>} */
    return (event) => {
      setTidalDrafts((previous) => ({ ...previous, [String(artistId)]: event.target.value }))
    }
  }

  const filteredArtists = useMemo(() => {
    const lowerQuery = query.trim().toLowerCase()
    if (!lowerQuery) return artists
    return artists.filter((artist) => {
      const name = String(artist.name ?? '').toLowerCase()
      const id = String(artist.id ?? '').toLowerCase()
      return name.includes(lowerQuery) || id.includes(lowerQuery)
    })
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
          <ButtonLink to="/history" title="Historico de downloads" icon="fas fa-clock-rotate-left" compact>
            Historico
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
              <Button onClick={onRefreshArtistsInfo} primary disabled={refreshingArtists || loading}>
                {refreshingArtists ? 'A atualizar...' : 'Atualizar info artistas'}
              </Button>
            </div>
            <div className="LocalTopRow__search">
              <Input value={searchQuery} onChange={onSearchQueryChange} placeholder="Nome no Tidal" />
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
                  {artist.image_url || artist.image_url ? (
                    <img
                      className="LocalArtistRow__avatar"
                      src={artist.image_url || artist.image_url}
                      alt={artist.name}
                    />
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
          <Input value={query} onChange={onFilterQueryChange} placeholder="Pesquisar por nome ou id" />
        </div>
        <p className="is-size-7 has-text-grey mb-3">
          Para puxar releases do Tidal, define o <strong>ID Tidal</strong> do artista (número na URL do perfil).
          Em listas antigas o número Tidal pode estar em «id» com «spotify_id»; o fetch de releases usa os dois.
        </p>
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
                  {artist.image_url || artist.image_url ? (
                    <img
                      className="LocalArtistRow__avatar"
                      src={artist.image_url || artist.image_url}
                      alt={artist.name}
                    />
                  ) : (
                    <div className="LocalArtistRow__avatar LocalArtistRow__avatar--placeholder" />
                  )}
                  <div>
                    <p className="LocalArtistRow__name">{artist.name}</p>
                    <code className="LocalArtistRow__id">{artist.id}</code>
                  </div>
                </div>
                <div className="field mt-2 mb-2">
                  <label className="label has-text-light is-size-7">ID Tidal (releases)</label>
                  <div className="is-flex" style={{ gap: '8px', flexWrap: 'wrap' }}>
                    <Input
                      value={tidalDrafts[String(artist.id)] ?? ''}
                      onChange={onTidalDraftInputChange(artist.id)}
                      placeholder="ex: 6951950"
                    />
                    <Button
                      onClick={() => onSaveTidalId(artist.id)}
                      className="LocalActionButton"
                      disabled={savingTidalId === String(artist.id)}
                    >
                      {savingTidalId === String(artist.id) ? 'A guardar…' : 'Guardar ID Tidal'}
                    </Button>
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
