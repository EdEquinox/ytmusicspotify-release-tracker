import { useEffect, useMemo, useState } from 'react'
import { ButtonLink, Content, Header, Input, VerticalLayout } from 'components/common'
import { listHistorico } from 'backendApi'

function HistoryDownloads() {
  const [items, setItems] = useState([])
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const loadHistory = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await listHistorico()
      setItems(Array.isArray(data) ? data : [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadHistory()
  }, [])

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    if (!normalized) return items
    return items.filter((item) => {
      const artist = String(item.artista || '').toLowerCase()
      const title = String(item.titulo || '').toLowerCase()
      const id = String(item.id || '').toLowerCase()
      return artist.includes(normalized) || title.includes(normalized) || id.includes(normalized)
    })
  }, [items, query])

  return (
    <VerticalLayout>
      <Header title="Historico de Downloads">
        <div className="Header__right">
          <ButtonLink to="/" title="Releases" icon="fas fa-music" compact>
            Releases
          </ButtonLink>
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
          <div className="LocalPanel mb-4">
            <div className="field mb-0">
              <label className="label has-text-light">Pesquisar no historico</label>
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Artista, musica ou id"
              />
            </div>
          </div>
          {error && <p className="has-text-danger">{error}</p>}
          {loading && <p className="has-text-grey">A carregar...</p>}
          {!loading && !filtered.length && <p className="has-text-grey">Sem itens no historico.</p>}

          {!loading && filtered.length > 0 && (
            <div className="table-container LocalTableWrap">
              <table className="table is-fullwidth is-striped LocalTable">
                <thead>
                  <tr>
                    <th>Artista</th>
                    <th>Musica</th>
                    <th>ID</th>
                    <th>Criado em</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((item) => (
                    <tr key={item.id}>
                      <td>{item.artista}</td>
                      <td>{item.titulo}</td>
                      <td>
                        <code>{item.id}</code>
                      </td>
                      <td>{item.created_at || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Content>
    </VerticalLayout>
  )
}

export default HistoryDownloads
