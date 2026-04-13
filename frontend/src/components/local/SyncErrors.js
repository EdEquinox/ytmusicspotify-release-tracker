import { useEffect, useState } from 'react'
import { Button, VerticalLayout, Header, Content, ButtonLink } from 'components/common'
import { deleteError, listErrors } from 'backendApi'

function SyncErrors() {
  const [errors, setErrors] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

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
          <div className="table-container LocalTableWrap">
            <table className="table is-fullwidth is-striped LocalTable">
              <thead>
                <tr>
                  <th>Musica</th>
                  <th>Artista</th>
                  <th>Album</th>
                  <th>Motivo</th>
                  <th>Criado em</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {errors.map((item) => (
                  <tr key={item.id}>
                    <td>{item.track_name}</td>
                    <td>{item.artist_name}</td>
                    <td>{item.album_name || '-'}</td>
                    <td>{item.reason}</td>
                    <td>{item.created_at}</td>
                    <td className="has-text-right">
                      <Button onClick={() => onDelete(item.id)} text>
                        Apagar
                      </Button>
                    </td>
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

export default SyncErrors
