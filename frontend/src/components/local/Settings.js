import { useEffect, useState } from 'react'
import { Button, ButtonLink, Content, Header, Input, VerticalLayout } from 'components/common'
import {
  getSettings,
  importArtists,
  importYTMusicAuth,
  updateSettings,
  validateYTMusicAuth,
} from 'backendApi'

const HelpLabel = ({ text, help }) => (
  <label className="label has-text-light" title={help}>
    {text}{' '}
    <span className="has-text-grey-light" style={{ cursor: 'help' }}>
      (?)
    </span>
  </label>
)

/**
 * Campos que a API ainda persiste mas já não fazem parte desta UI
 * (sem Spotify; fetch automático desligado — sessão Tidal expira).
 */
const STATIC_PERSISTED_SETTINGS = {
  auto_fetch_enabled: false,
  auto_fetch_time: '04:00',
  auto_fetch_window_days: 1,
  spotify_include_groups: 'album,single',
  spotify_market: '',
  spotify_client_id: '',
  spotify_client_secret: '',
  spotify_oauth_client_id: '',
  spotify_oauth_redirect_uri: '',
  reverse_spotify_playlist_id: '',
  reverse_spotify_redirect_uri: 'http://localhost:8080/callback',
  reverse_spotify_add_to_playlist: false,
  reverse_tidal_only: true,
}

/** @param {Record<string, unknown>} settings */
function mapSettingsToForm(settings) {
  return {
    playlist_id: settings.playlist_id || '',
    ytmusic_user: settings.ytmusic_user || '',
    reverse_ytmusic_user: settings.reverse_ytmusic_user || '',
    local_fetch_spacing_ms: Number(settings.local_fetch_spacing_ms || 120),
    release_workers: Number(settings.release_workers || 10),
    worker_idle_seconds: Number(settings.worker_idle_seconds || 20),
    worker_processed_sleep_seconds: Number(settings.worker_processed_sleep_seconds || 10),
    worker_backend_retry_seconds: Number(settings.worker_backend_retry_seconds || 15),
    worker_album_audio_only_strict:
      settings.worker_album_audio_only_strict === undefined
        ? true
        : Boolean(settings.worker_album_audio_only_strict),
    reverse_poll_seconds: Number(settings.reverse_poll_seconds || 300),
    reverse_liked_limit: Number(settings.reverse_liked_limit || 100),
    reverse_spotiflac_enabled: Boolean(settings.reverse_spotiflac_enabled),
    reverse_spotiflac_output_dir: settings.reverse_spotiflac_output_dir || '/data/downloads',
    reverse_spotiflac_command_template:
      settings.reverse_spotiflac_command_template ||
      'spotiflac "{spotify_url}" "{output_dir}"',
    reverse_spotiflac_timeout_seconds: Number(settings.reverse_spotiflac_timeout_seconds || 600),
    reverse_spotiflac_loop_minutes: Number(settings.reverse_spotiflac_loop_minutes || 0),
    reverse_track_spacing_ms: Number(settings.reverse_track_spacing_ms || 0),
  }
}

function Settings() {
  const [form, setForm] = useState(() => mapSettingsToForm({}))
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [infoMessage, setInfoMessage] = useState('')
  const [importingArtistsJson, setImportingArtistsJson] = useState(false)
  const [importingAuthJson, setImportingAuthJson] = useState(false)
  const [validatingAuthJson, setValidatingAuthJson] = useState(false)
  const [importingSettingsJson, setImportingSettingsJson] = useState(false)

  useEffect(() => {
    async function load() {
      setLoading(true)
      setError('')
      try {
        const settings = await getSettings()
        setForm(mapSettingsToForm(settings))
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const onSubmit = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError('')
    setInfoMessage('')
    try {
      await updateSettings({
        ...STATIC_PERSISTED_SETTINGS,
        playlist_id: form.playlist_id,
        ytmusic_user: form.ytmusic_user,
        reverse_ytmusic_user: form.reverse_ytmusic_user,
        local_fetch_spacing_ms: Number(form.local_fetch_spacing_ms || 0),
        release_workers: Number(form.release_workers || 1),
        worker_idle_seconds: Number(form.worker_idle_seconds || 20),
        worker_processed_sleep_seconds: Number(form.worker_processed_sleep_seconds || 10),
        worker_backend_retry_seconds: Number(form.worker_backend_retry_seconds || 15),
        worker_album_audio_only_strict: Boolean(form.worker_album_audio_only_strict),
        reverse_poll_seconds: Number(form.reverse_poll_seconds || 300),
        reverse_liked_limit: Number(form.reverse_liked_limit || 100),
        reverse_spotiflac_enabled: Boolean(form.reverse_spotiflac_enabled),
        reverse_spotiflac_output_dir: form.reverse_spotiflac_output_dir,
        reverse_spotiflac_command_template: form.reverse_spotiflac_command_template,
        reverse_spotiflac_timeout_seconds: Number(form.reverse_spotiflac_timeout_seconds || 600),
        reverse_spotiflac_loop_minutes: Number(form.reverse_spotiflac_loop_minutes || 0),
        reverse_track_spacing_ms: Number(form.reverse_track_spacing_ms || 0),
      })
      setInfoMessage('Settings guardadas com sucesso.')
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const onImportArtistsJson = async (event) => {
    const file = event.target.files?.[0]
    if (!file) return
    setImportingArtistsJson(true)
    setError('')
    setInfoMessage('')
    try {
      const text = await file.text()
      const parsed = JSON.parse(text)
      if (!Array.isArray(parsed)) throw new Error('O ficheiro de artistas deve conter um array JSON.')
      await importArtists({ artists: parsed, replace: false })
      setInfoMessage(`Importacao de artistas concluida (${parsed.length} entradas lidas).`)
    } catch (err) {
      setError(err.message)
    } finally {
      setImportingArtistsJson(false)
      event.target.value = ''
    }
  }

  const onImportYTMusicAuthJson = async (event) => {
    const file = event.target.files?.[0]
    if (!file) return
    setImportingAuthJson(true)
    setError('')
    setInfoMessage('')
    try {
      const text = await file.text()
      const parsed = JSON.parse(text)
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        throw new Error('O ficheiro de auth deve conter um objeto JSON.')
      }
      const response = await importYTMusicAuth(parsed)
      const updatedFiles = response?.updated_files ? ` (${response.updated_files})` : ''
      setInfoMessage(`Auth do YTMusic importada com sucesso para os workers.${updatedFiles}`)
    } catch (err) {
      setError(err.message)
    } finally {
      setImportingAuthJson(false)
      event.target.value = ''
    }
  }

  const onImportSettingsJson = async (event) => {
    const file = event.target.files?.[0]
    if (!file) return
    setImportingSettingsJson(true)
    setError('')
    setInfoMessage('')
    try {
      const text = await file.text()
      const parsed = JSON.parse(text)
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        throw new Error('O ficheiro de settings deve conter um objeto JSON.')
      }
      const saved = await updateSettings(parsed)
      setForm(mapSettingsToForm(saved))
      setInfoMessage('Settings importadas com sucesso.')
    } catch (err) {
      setError(err.message)
    } finally {
      setImportingSettingsJson(false)
      event.target.value = ''
    }
  }

  const onValidateYTMusicAuth = async () => {
    setValidatingAuthJson(true)
    setError('')
    setInfoMessage('')
    try {
      const result = await validateYTMusicAuth()
      const details = (result.results || [])
        .map((item) => `${item.ok ? 'OK' : 'ERRO'}: ${item.target} -> ${item.message}`)
        .join(' | ')
      if (result.ok) {
        setInfoMessage(`Auth YTMusic valida para todos os workers. ${details}`)
      } else {
        setError(`Falha na validacao da auth YTMusic. ${details}`)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setValidatingAuthJson(false)
    }
  }

  return (
    <VerticalLayout>
      <Header title="Settings">
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
          <ButtonLink to="/setup" title="Guia de configuracao" icon="fas fa-circle-info" compact>
            Guia
          </ButtonLink>
        </div>
      </Header>
      <Content>
        <div className="LocalPage">
          <form className="LocalPanel" onSubmit={onSubmit}>
            <h3 className="title is-6 has-text-light mb-3">YouTube Music — playlist principal</h3>
            <p className="has-text-grey is-size-7 mb-3">
              O worker principal usa esta playlist e o JSON de auth importado abaixo. O login Tidal faz-se na página
              Releases (a sessão expira; usa fetch manual quando precisares).
            </p>
            <div className="field mb-5">
              <HelpLabel
                text="Playlist ID do YouTube Music"
                help="Playlist de destino usada pelo worker principal para adicionar faixas."
              />
              <Input
                value={form.playlist_id}
                onChange={(event) => setForm((prev) => ({ ...prev, playlist_id: event.target.value }))}
                placeholder="Ex: PLxxxxxxxxxxxxxxxxxxxx"
              />
            </div>
            <div className="field mb-4">
              <HelpLabel
                text="YTMusic — user ID (opcional)"
                help="Só para conta de marca (brand): ID na URL em myaccount.google.com/brandaccounts. Várias contas Google pessoais: usa x-goog-authuser no JSON de auth. Se vazio, usa YTMUSIC_USER do ambiente (se existir)."
              />
              <Input
                value={form.ytmusic_user}
                onChange={(event) => setForm((prev) => ({ ...prev, ytmusic_user: event.target.value }))}
                placeholder="Vazio = conta predefinida / env"
              />
            </div>
            <div className="field mb-5">
              <HelpLabel
                text="YTMusic reverse — user ID (opcional)"
                help="Igual ao anterior, mas para o ficheiro REVERSE_YTMUSIC_AUTH_FILE quando é diferente do principal. Se vazio, reutiliza o user principal em cima, depois REVERSE_YTMUSIC_USER / YTMUSIC_USER no ambiente."
              />
              <Input
                value={form.reverse_ytmusic_user}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, reverse_ytmusic_user: event.target.value }))
                }
                placeholder="Vazio = mesmo que principal / env"
              />
            </div>

            <h3 className="title is-6 has-text-light mb-3">Importar dados (JSON)</h3>
            <div className="columns is-multiline mb-5">
              <div className="column is-4-desktop is-12-tablet">
                <label className="label has-text-light">Artistas</label>
                <input type="file" accept=".json,application/json" onChange={onImportArtistsJson} />
                {importingArtistsJson && <p className="has-text-grey is-size-7 mt-1">A importar artistas...</p>}
              </div>
              <div className="column is-4-desktop is-12-tablet">
                <label className="label has-text-light">Auth YTMusic</label>
                <input type="file" accept=".json,application/json" onChange={onImportYTMusicAuthJson} />
                {importingAuthJson && <p className="has-text-grey is-size-7 mt-1">A importar auth...</p>}
                <div className="mt-2">
                  <Button
                    type="button"
                    onClick={onValidateYTMusicAuth}
                    disabled={validatingAuthJson || loading}
                  >
                    {validatingAuthJson ? 'A validar...' : 'Validar auth YTMusic'}
                  </Button>
                  <p className="has-text-grey is-size-7 mt-1">
                    A validação usa os user IDs já gravados com Gravar, não rascunhos só no formulário.
                  </p>
                </div>
              </div>
              <div className="column is-4-desktop is-12-tablet">
                <label className="label has-text-light">Settings</label>
                <input type="file" accept=".json,application/json" onChange={onImportSettingsJson} />
                {importingSettingsJson && <p className="has-text-grey is-size-7 mt-1">A importar settings...</p>}
              </div>
            </div>

            <h3 className="title is-6 has-text-light mb-3">Workers e performance</h3>
            <p className="has-text-grey is-size-7 mb-3">
              Worker principal (fila YTMusic), pedidos ao backend/Tidal e reverse worker (likes + SpotiFLAC). Mais
              pausa e menos paralelismo reduzem erros por limite de pedidos.
            </p>

            <h4 className="title is-7 has-text-grey-light mb-2">Worker principal e backend</h4>
            <div className="columns is-multiline mb-4">
              <div className="column is-3-desktop is-6-tablet">
                <HelpLabel
                  text="Fila vazia — espera (s)"
                  help="Quando a fila csv_releases não tem itens, quanto tempo o worker dorme antes de voltar a perguntar."
                />
                <Input
                  type="number"
                  min="5"
                  max="3600"
                  value={form.worker_idle_seconds}
                  onChange={(event) =>
                    setForm((prev) => ({
                      ...prev,
                      worker_idle_seconds: Number(event.target.value || 20),
                    }))
                  }
                />
              </div>
              <div className="column is-3-desktop is-6-tablet">
                <HelpLabel
                  text="Após processar — espera (s)"
                  help="Pausa depois de processar itens antes de verificar de novo a fila."
                />
                <Input
                  type="number"
                  min="1"
                  max="600"
                  value={form.worker_processed_sleep_seconds}
                  onChange={(event) =>
                    setForm((prev) => ({
                      ...prev,
                      worker_processed_sleep_seconds: Number(event.target.value || 10),
                    }))
                  }
                />
              </div>
              <div className="column is-3-desktop is-6-tablet">
                <HelpLabel
                  text="Erro ao falar com API — retry (s)"
                  help="Espera quando o worker principal não consegue contactar o backend."
                />
                <Input
                  type="number"
                  min="5"
                  max="600"
                  value={form.worker_backend_retry_seconds}
                  onChange={(event) =>
                    setForm((prev) => ({
                      ...prev,
                      worker_backend_retry_seconds: Number(event.target.value || 15),
                    }))
                  }
                />
              </div>
              <div className="column is-3-desktop is-12-tablet">
                <HelpLabel
                  text="Álbuns só áudio (strict)"
                  help="Se ativo, evita vídeos musicais em álbuns e tenta fallback por faixa."
                />
                <label className="checkbox has-text-light mt-2">
                  <input
                    type="checkbox"
                    checked={form.worker_album_audio_only_strict}
                    onChange={(event) =>
                      setForm((prev) => ({
                        ...prev,
                        worker_album_audio_only_strict: event.target.checked,
                      }))
                    }
                  />{' '}
                  Modo strict
                </label>
              </div>
            </div>

            <h4 className="title is-7 has-text-grey-light mb-2">Fetch de releases (Tidal no backend)</h4>
            <div className="columns is-multiline mb-4">
              <div className="column is-4-desktop is-6-tablet">
                <HelpLabel
                  text="Pausa entre artistas (ms)"
                  help="No fetch local sequencial, pausa entre cada artista para não sobrecarregar o Tidal."
                />
                <Input
                  type="number"
                  min="0"
                  max="5000"
                  value={form.local_fetch_spacing_ms}
                  onChange={(event) =>
                    setForm((prev) => ({
                      ...prev,
                      local_fetch_spacing_ms: Number(event.target.value || 0),
                    }))
                  }
                />
              </div>
              <div className="column is-4-desktop is-6-tablet">
                <HelpLabel
                  text="Workers paralelos"
                  help="Número de pedidos Tidal em paralelo ao listar catálogo (mais = mais rápido, mais carga)."
                />
                <Input
                  type="number"
                  min="1"
                  max="30"
                  value={form.release_workers}
                  onChange={(event) =>
                    setForm((prev) => ({
                      ...prev,
                      release_workers: Number(event.target.value || 1),
                    }))
                  }
                />
              </div>
            </div>

            <h4 className="title is-7 has-text-grey-light mb-2">Reverse worker (likes YTMusic + SpotiFLAC)</h4>
            <div className="columns is-multiline mb-2">
              <div className="column is-3-desktop is-6-tablet">
                <HelpLabel
                  text="Intervalo entre ciclos (s)"
                  help="Tempo entre cada passagem pelos likes no YouTube Music."
                />
                <Input
                  type="number"
                  min="30"
                  max="86400"
                  value={form.reverse_poll_seconds}
                  onChange={(event) =>
                    setForm((prev) => ({
                      ...prev,
                      reverse_poll_seconds: Number(event.target.value || 300),
                    }))
                  }
                />
              </div>
              <div className="column is-3-desktop is-6-tablet">
                <HelpLabel
                  text="Máx. likes por ciclo"
                  help="Quantos likes são lidos de cada vez no YTMusic."
                />
                <Input
                  type="number"
                  min="1"
                  max="5000"
                  value={form.reverse_liked_limit}
                  onChange={(event) =>
                    setForm((prev) => ({
                      ...prev,
                      reverse_liked_limit: Number(event.target.value || 100),
                    }))
                  }
                />
              </div>
              <div className="column is-3-desktop is-6-tablet">
                <HelpLabel
                  text="Pausa entre faixas (ms)"
                  help="Entre downloads/processamento de cada like no reverse worker."
                />
                <Input
                  type="number"
                  min="0"
                  max="30000"
                  value={form.reverse_track_spacing_ms}
                  onChange={(event) =>
                    setForm((prev) => ({
                      ...prev,
                      reverse_track_spacing_ms: Number(event.target.value || 0),
                    }))
                  }
                />
              </div>
              <div className="column is-3-desktop is-6-tablet">
                <HelpLabel
                  text="SpotiFLAC — timeout (s)"
                  help="Tempo máximo por execução de download antes de marcar erro."
                />
                <Input
                  type="number"
                  min="10"
                  max="86400"
                  value={form.reverse_spotiflac_timeout_seconds}
                  onChange={(event) =>
                    setForm((prev) => ({
                      ...prev,
                      reverse_spotiflac_timeout_seconds: Number(event.target.value || 600),
                    }))
                  }
                />
              </div>
            </div>
            <div className="columns is-multiline mb-3">
              <div className="column is-3-desktop is-6-tablet">
                <HelpLabel
                  text="SpotiFLAC — loop (min)"
                  help="0 = uma execução por ciclo; maior que 0 deixa o SpotiFLAC em loop interno."
                />
                <Input
                  type="number"
                  min="0"
                  max="1440"
                  value={form.reverse_spotiflac_loop_minutes}
                  onChange={(event) =>
                    setForm((prev) => ({
                      ...prev,
                      reverse_spotiflac_loop_minutes: Number(event.target.value || 0),
                    }))
                  }
                />
              </div>
              <div className="column is-9-desktop is-12-tablet is-flex is-align-items-flex-end">
                <label className="checkbox has-text-light">
                  <input
                    type="checkbox"
                    checked={form.reverse_spotiflac_enabled}
                    onChange={(event) =>
                      setForm((prev) => ({ ...prev, reverse_spotiflac_enabled: event.target.checked }))
                    }
                  />{' '}
                  Ativar download via SpotiFLAC (só marca processado após ficheiro válido)
                </label>
              </div>
            </div>

            <div className="columns is-multiline mb-2">
              <div className="column is-5-desktop is-12-tablet">
                <HelpLabel
                  text="SpotiFLAC — pasta de saída"
                  help="Diretório no contentor onde gravar descargas (volume persistente)."
                />
                <Input
                  value={form.reverse_spotiflac_output_dir}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, reverse_spotiflac_output_dir: event.target.value }))
                  }
                  placeholder="/data/downloads"
                />
              </div>
              <div className="column is-7-desktop is-12-tablet">
                <HelpLabel
                  text="Comando SpotiFLAC"
                  help="Placeholders: {spotify_url} (URL Tidal ou outro), {output_dir}, {artist}, {title}."
                />
                <Input
                  value={form.reverse_spotiflac_command_template}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, reverse_spotiflac_command_template: event.target.value }))
                  }
                  placeholder={'spotiflac "{spotify_url}" "{output_dir}"'}
                />
              </div>
            </div>
            <p className="has-text-grey is-size-7 mb-4">
              Erros de download aparecem em Erros com tipo <code>DOWNLOAD_SPOTIFLAC</code>. O reverse usa só Tidal
              (pesquisa no backend + <code>playlist_track_links.json</code>).
            </p>

            {error && <p className="has-text-danger mb-3">{error}</p>}
            {infoMessage && <p className="has-text-success mb-3">{infoMessage}</p>}
            {loading && <p className="has-text-grey mb-3">A carregar settings...</p>}

            <Button type="submit" primary disabled={saving || loading}>
              {saving ? 'A guardar...' : 'Guardar settings'}
            </Button>
          </form>
        </div>
      </Content>
    </VerticalLayout>
  )
}

export default Settings
