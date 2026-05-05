import { useEffect, useState } from 'react'
import { Button, VerticalLayout, Header, Content, ButtonLink } from 'components/common'
import { listErrors, resolveError, updateErrorLinks } from 'backendApi'

function SyncErrors() {
  const [errors, setErrors] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')
  const [manualLinks, setManualLinks] = useState({})
  const [savingLinksById, setSavingLinksById] = useState({})
  const [resolvingById, setResolvingById] = useState({})
  const [infoMessage, setInfoMessage] = useState('')

  const loadErrors = async () => {
    setLoading(true)
    setError('')
    setInfoMessage('')
    try {
      const data = await listErrors()
      setErrors(data)
      const nextManualLinks = {}
      for (const item of data) {
        nextManualLinks[item.id] = {
          spotify: item.spotify_url_manual || '',
          tidal: item.tidal_url_manual || '',
        }
      }
      setManualLinks(nextManualLinks)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadErrors()
  }, [])

  const onResolve = async (errorId) => {
    setError('')
    setInfoMessage('')
    setResolvingById((current) => ({ ...current, [errorId]: true }))
    try {
      const result = await resolveError(errorId)
      if (result?.csv_removed) {
        setInfoMessage('Erro removido e entrada retirada da fila CSV.')
      } else {
        setInfoMessage('Erro marcado como resolvido.')
      }
      await loadErrors()
    } catch (err) {
      setError(err.message)
    } finally {
      setResolvingById((current) => ({ ...current, [errorId]: false }))
    }
  }

  const onChangeManualLink = (errorId, service, value) => {
    setManualLinks((current) => ({
      ...current,
      [errorId]: {
        spotify: current[errorId]?.spotify || '',
        tidal: current[errorId]?.tidal || '',
        [service]: value,
      },
    }))
  }

  const hasSpotifyNotFoundError = (reason) => {
    const normalized = String(reason || '').toLowerCase()
    return normalized.includes('nao_no_spotify') || normalized.includes('nao encontrada no spotify')
  }

  const hasTidalNotFoundError = (reason) => {
    const normalized = String(reason || '').toLowerCase()
    return (
      normalized.includes('tidal') &&
      (normalized.includes('not found') ||
        normalized.includes('nao encontrada') ||
        normalized.includes('could not find'))
    )
  }

  const onSaveManualLinks = async (item) => {
    const payload = {
      spotify_url_manual: (manualLinks[item.id]?.spotify || '').trim() || null,
      tidal_url_manual: (manualLinks[item.id]?.tidal || '').trim() || null,
    }
    setSavingLinksById((current) => ({ ...current, [item.id]: true }))
    setError('')
    try {
      await updateErrorLinks(item.id, payload)
      await loadErrors()
    } catch (err) {
      setError(err.message)
    } finally {
      setSavingLinksById((current) => ({ ...current, [item.id]: false }))
    }
  }

  const inferErrorType = (reason) => {
    const value = String(reason || '').trim()
    if (!value) return 'OUTRO'
    const matched = value.match(/^([A-Z_]+)\s*:/)
    return matched?.[1] || 'OUTRO'
  }

  const filteredErrors = errors.filter((item) => {
    if (typeFilter === 'all') return true
    return inferErrorType(item.reason) === typeFilter
  })

  const errorTypes = Array.from(new Set(errors.map((item) => inferErrorType(item.reason)))).sort()

  return (
    <VerticalLayout>
      <Header title="Erros de Sincronizacao">
        <div className="Header__right">
          <ButtonLink to="/" title="Releases" icon="fas fa-music" compact>
            Releases
          </ButtonLink>
          <ButtonLink to="/artists" title="Gerir artistas" icon="fas fa-users" compact>
            Artistas
          </ButtonLink>
          <ButtonLink to="/settings" title="Settings" icon="fas fa-gear" compact>
            Settings
          </ButtonLink>
          <ButtonLink to="/history" title="Historico de downloads" icon="fas fa-clock-rotate-left" compact>
            Historico
          </ButtonLink>
          <ButtonLink to="/setup" title="Guia de configuracao" icon="fas fa-circle-info" compact>
            Guia
          </ButtonLink>
        </div>
      </Header>
      <Content>
        <div className="LocalPage">
        {error && <p className="has-text-danger">{error}</p>}
        {infoMessage && <p className="has-text-info">{infoMessage}</p>}
        {loading && <p className="has-text-grey">A carregar...</p>}
        {!loading && !errors.length && <p className="has-text-grey">Sem erros pendentes.</p>}

        {!loading && errors.length > 0 && (
          <>
            <div className="LocalPanel mb-3">
              <div className="field mb-0" style={{ maxWidth: 300 }}>
                <label className="label has-text-light">Tipo de erro</label>
                <div className="select is-fullwidth">
                  <select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}>
                    <option value="all">Todos</option>
                    {errorTypes.map((item) => (
                      <option key={item} value={item}>
                        {item}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            {!filteredErrors.length && <p className="has-text-grey">Sem erros para este filtro.</p>}

            {filteredErrors.length > 0 && (
              <div className="LocalErrorGrid">
                {filteredErrors.map((item) => (
                  <article className="LocalErrorCard" key={item.id}>
                    <p className="LocalReleaseDateBadge">
                      {inferErrorType(item.reason)}{item.created_at ? ` - ${item.created_at}` : ''}
                    </p>
                    <p className="LocalReleaseReason">
                      Tentativas: {Math.max(Number(item.attempts) || 1, 1)}
                    </p>
                    <p className="LocalReleaseTitle">{item.track_name || 'Sem musica'}</p>
                    <p className="LocalReleaseArtist">{item.artist_name || 'Sem artista'}</p>
                    <p className="LocalReleaseReason">{item.album_name ? `Album: ${item.album_name}` : 'Album: -'}</p>
                    <p className="LocalErrorReason">{item.reason}</p>
                    {Boolean(item.release_id) && (
                      <p className="LocalReleaseReason is-size-7 has-text-warning">
                        Ao marcar como resolvido, a entrada correspondente e tambem removida de{' '}
                        <code>csv_releases.json</code> (deixa de ser processada pelo worker).
                      </p>
                    )}
                    {(hasSpotifyNotFoundError(item.reason) || hasTidalNotFoundError(item.reason)) && (
                      <div className="mt-3">
                        {hasSpotifyNotFoundError(item.reason) && (
                          <div className="field">
                            <label className="label has-text-light">URL Open Spotify (fallback)</label>
                            <div className="control">
                              <input
                                className="input"
                                type="url"
                                placeholder="https://open.spotify.com/track/..."
                                value={manualLinks[item.id]?.spotify || ''}
                                onChange={(event) =>
                                  onChangeManualLink(item.id, 'spotify', event.target.value)
                                }
                              />
                            </div>
                          </div>
                        )}
                        {hasTidalNotFoundError(item.reason) && (
                          <div className="field">
                            <label className="label has-text-light">Link manual Tidal</label>
                            <div className="control">
                              <input
                                className="input"
                                type="url"
                                placeholder="https://listen.tidal.com/..."
                                value={manualLinks[item.id]?.tidal || ''}
                                onChange={(event) =>
                                  onChangeManualLink(item.id, 'tidal', event.target.value)
                                }
                              />
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                    <div className="LocalErrorActions">
                      {(hasSpotifyNotFoundError(item.reason) || hasTidalNotFoundError(item.reason)) && (
                        <Button
                          className="LocalActionButton"
                          onClick={() => onSaveManualLinks(item)}
                          disabled={Boolean(savingLinksById[item.id])}
                        >
                          {savingLinksById[item.id] ? 'A guardar...' : 'Guardar links'}
                        </Button>
                      )}
                      <Button
                        className="LocalActionButton is-primary"
                        onClick={() => onResolve(item.id)}
                        disabled={Boolean(resolvingById[item.id])}
                      >
                        {resolvingById[item.id] ? 'A resolver...' : 'Marcar como resolvido'}
                      </Button>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </>
        )}
        </div>
      </Content>
    </VerticalLayout>
  )
}

export default SyncErrors
