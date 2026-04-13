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
              Copia <code>.env.example</code> para <code>.env</code> e preenche pelo menos:
            </p>
            <ul className="has-text-grey-light">
              <li>SPOTIFY_CLIENT_ID e SPOTIFY_CLIENT_SECRET</li>
              <li>REACT_APP_SPOTIFY_CLIENT_ID e REACT_APP_SPOTIFY_REDIRECT_URI</li>
              <li>YTMUSIC_AUTH_FILE (normalmente /data/ytmusic_auth.json)</li>
            </ul>
          </div>

          <div className="LocalPanel mb-4">
            <h3 className="title is-6 has-text-light">3) Spotify Dashboard</h3>
            <p className="has-text-grey-light">
              Cria uma app no Spotify Developer Dashboard e adiciona exatamente o redirect URI usado no frontend.
            </p>
            <p className="has-text-grey-light">
              Exemplo: <code>http://127.0.0.1:3001/artists</code>
            </p>
          </div>

          <div className="LocalPanel mb-4">
            <h3 className="title is-6 has-text-light">4) Auth do YouTube Music</h3>
            <p className="has-text-grey-light">
              Coloca o ficheiro de auth em <code>data/ytmusic_auth.json</code> (cookie headers exportados do browser).
              Define playlist/user no separador <code>Settings</code>.
            </p>
          </div>

          <div className="LocalPanel mb-4">
            <h3 className="title is-6 has-text-light">5) Arrancar app</h3>
            <pre className="has-text-grey-light">docker compose up --build</pre>
            <p className="has-text-grey-light">
              Frontend: <code>http://127.0.0.1:3001</code>
            </p>
          </div>

          <div className="LocalPanel">
            <h3 className="title is-6 has-text-light">6) Troubleshooting rapido</h3>
            <ul className="has-text-grey-light">
              <li>Se houver 429 no Spotify, aumenta delay e reduz workers em Settings.</li>
              <li>Se settings nao gravarem, corrige permissoes da pasta data no host.</li>
              <li>Se worker nao adicionar musicas, valida auth file e playlist ID.</li>
            </ul>
          </div>

          <div className="LocalPanel mt-4">
            <h3 className="title is-6 has-text-light">7) Deploy em Portainer (servidor)</h3>
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
