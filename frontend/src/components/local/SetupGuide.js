import { Content, Header, HeaderNav, VerticalLayout } from 'components/common'

function SetupGuide() {
  return (
    <VerticalLayout>
      <Header>
        <HeaderNav />
      </Header>
      <Content>
        <div className="LocalPage">
          <div className="LocalPanel mb-4">
            <h3 className="title is-6 has-text-light">Resumo</h3>
            <p className="has-text-grey-light">
              Segues artistas no Tidal, vês lancamentos novos, e envias faixas para uma playlist do YouTube Music. O
              worker trata da fila em segundo plano.
            </p>
          </div>

          <div className="LocalPanel mb-4">
            <h3 className="title is-6 has-text-light">1) Settings</h3>
            <ul className="has-text-grey-light">
              <li>Define o Playlist ID do YouTube Music de destino.</li>
              <li>Se usares conta brand, preenche o user ID do YTMusic.</li>
              <li>Importa o JSON de auth do YTMusic e valida-o.</li>
            </ul>
          </div>

          <div className="LocalPanel mb-4">
            <h3 className="title is-6 has-text-light">2) Login Tidal</h3>
            <p className="has-text-grey-light">
              Em <strong>Releases</strong>, inicia sessao Tidal (login por dispositivo). A sessao expira; quando o
              fetch falhar por autenticacao, volta a fazer login.
            </p>
          </div>

          <div className="LocalPanel mb-4">
            <h3 className="title is-6 has-text-light">3) Artistas</h3>
            <p className="has-text-grey-light">
              Em <strong>Artistas</strong>, pesquisa no Tidal e adiciona quem queres seguir. Cada artista precisa de ID
              Tidal para o fetch encontrar lancamentos.
            </p>
          </div>

          <div className="LocalPanel mb-4">
            <h3 className="title is-6 has-text-light">4) Fetch de releases</h3>
            <ol className="has-text-grey-light">
              <li>Em <strong>Releases</strong>, escolhe o intervalo de datas e faz Fetch.</li>
              <li>Os resultados aparecem agrupados por dia em que o fetch correu.</li>
              <li>
                Usa filtros (pesquisa, dia de fetch, excluir remix / various artists / duplicados) para afinar a lista.
              </li>
              <li>
                Para limpar um batch antigo, usa <strong>Delete</strong> na linha da data desse fetch.
              </li>
            </ol>
          </div>

          <div className="LocalPanel mb-4">
            <h3 className="title is-6 has-text-light">5) Enviar para a playlist</h3>
            <p className="has-text-grey-light">
              Em cada release (ou faixa expandida de um album), adiciona a playlist. Isso mete o item na fila; o worker
              procura no YouTube Music e adiciona a playlist definida em Settings.
            </p>
          </div>

          <div className="LocalPanel">
            <h3 className="title is-6 has-text-light">6) Erros e historico</h3>
            <ul className="has-text-grey-light">
              <li>
                <strong>Erros</strong> — falhas ao sincronizar com o YouTube Music (podes corrigir links manuais e
                resolver).
              </li>
              <li>
                <strong>Historico</strong> — o que o worker ja processou com sucesso.
              </li>
            </ul>
          </div>
        </div>
      </Content>
    </VerticalLayout>
  )
}

export default SetupGuide
