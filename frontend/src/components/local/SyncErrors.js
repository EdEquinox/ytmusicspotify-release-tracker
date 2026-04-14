import { useEffect, useState } from 'react'
import { Button, VerticalLayout, Header, Content, ButtonLink } from 'components/common'
import { deleteError, listErrors } from 'backendApi'

function SyncErrors() {
  const [errors, setErrors] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')

  const loadErrors = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await listErrors()
      setErrors(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadErrors()
  }, [])

  const onDelete = async (errorId) => {
    setError('')
    try {
      await deleteError(errorId)
      await loadErrors()
    } catch (err) {
      setError(err.message)
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
                    <div className="LocalErrorActions">
                      <Button className="LocalActionButton" onClick={() => onDelete(item.id)}>
                        Apagar
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
