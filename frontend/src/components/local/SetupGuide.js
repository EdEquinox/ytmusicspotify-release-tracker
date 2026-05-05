import { ButtonLink, Content, Header, VerticalLayout } from 'components/common'

function SetupGuide() {
  return (
    <VerticalLayout>
      <Header title="Guia de Configuracao">
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
          <ButtonLink to="/history" title="Historico de downloads" icon="fas fa-clock-rotate-left" compact>
            Historico
          </ButtonLink>
          <ButtonLink to="/settings" title="Settings" icon="fas fa-gear" compact>
            Settings
          </ButtonLink>
        </div>
      </Header>
      <Content>
        <div className="LocalPage">
          <div className="LocalPanel mb-4">
            <h3 className="title is-6 has-text-light">1) Requisitos</h3>
            <p className="has-text-grey-light">
              Instala Docker e Docker Compose. Esta app foi pensada para correr localmente com containers.
            </p>
          </div>

          <div className="LocalPanel mb-4">
            <h3 className="title is-6 has-text-light">2) Preparar .env</h3>
            <p className="has-text-grey-light">
              Copia <code>.env.example</code> para <code>.env</code>. Para Tidal + YTMusic basta auth, backend URL e
              volumes de <code>data/</code>.
            </p>
            <ul className="has-text-grey-light">
              <li>
                <code>YTMUSIC_AUTH_FILE</code> (normalmente <code>/data/ytmusic_auth.json</code>) e{' '}
                <code>REACT_APP_BACKEND_URL</code> se o frontend nao falar com o backend na porta por defeito.
              </li>
            </ul>
          </div>

          <div className="LocalPanel mb-4">
            <h3 className="title is-6 has-text-light">3) Auth do YouTube Music e playlist</h3>
            <p className="has-text-grey-light">
              Importa o JSON de auth em <code>Settings</code> ou coloca o ficheiro em{' '}
              <code>data/ytmusic_auth.json</code>. Define o <strong>Playlist ID</strong> de destino no mesmo ecra.
            </p>
            <p className="has-text-grey-light">
              Em <code>Releases</code> inicia sessao Tidal (login por dispositivo) para puxar lancamentos; em{' '}
              <code>Gerir Artistas</code> associa o ID Tidal a cada artista.
            </p>
          </div>

          <div className="LocalPanel mb-4">
            <h3 className="title is-6 has-text-light">4) Arrancar app</h3>
            <pre className="has-text-grey-light">docker compose up --build</pre>
            <p className="has-text-grey-light">
              Frontend: <code>http://127.0.0.1:3001</code>
            </p>
          </div>

          <div className="LocalPanel">
            <h3 className="title is-6 has-text-light">5) Troubleshooting rapido</h3>
            <ul className="has-text-grey-light">
              <li>Se o fetch Tidal falhar ou for lento, aumenta o delay entre artistas e reduz workers em Settings.</li>
              <li>Se settings nao gravarem, corrige permissoes da pasta data no host.</li>
              <li>Se o worker nao adicionar musicas, valida auth YTMusic e playlist ID.</li>
            </ul>
          </div>

          <div className="LocalPanel mt-4">
            <h3 className="title is-6 has-text-light">6) Deploy em Portainer (servidor)</h3>
            <ol className="has-text-grey-light">
              <li>Publica as 3 imagens num registry (frontend/backend/worker).</li>
              <li>Copia <code>.env.portainer.example</code> para variaveis do Stack e ajusta dominios/ports.</li>
              <li>Cria no servidor: <code>/opt/ytmusic-release-tracker/data</code>.</li>
              <li>Garante permissoes de escrita nessa pasta para evitar erro em settings.json.</li>
              <li>
                No Portainer, cria um Stack com o ficheiro <code>docker-compose.portainer.yml</code> e faz deploy.
              </li>
            </ol>
          </div>
        </div>
      </Content>
    </VerticalLayout>
  )
}

export default SetupGuide
