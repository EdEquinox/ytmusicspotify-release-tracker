import { useEffect, useState } from 'react'
import { Button, ButtonLink, Content, Header, Input, VerticalLayout } from 'components/common'
import {
  completeReverseSpotifyOAuth,
  getSettings,
  importArtists,
  importYTMusicAuth,
  updateSettings,
  validateYTMusicAuth,
} from 'backendApi'

const SPOTIFY_GROUP_OPTIONS = ['album', 'single', 'compilation', 'appears_on']
const SPOTIFY_MARKET_OPTIONS = ['', 'PT', 'BR', 'US', 'GB', 'ES', 'FR', 'DE', 'IT', 'JP']
const HOUR_OPTIONS = Array.from({ length: 24 }, (_, idx) => String(idx).padStart(2, '0'))
const MINUTE_OPTIONS = Array.from({ length: 12 }, (_, idx) => String(idx * 5).padStart(2, '0'))

const HelpLabel = ({ text, help }) => (
  <label className="label has-text-light" title={help}>
    {text}{' '}
    <span className="has-text-grey-light" style={{ cursor: 'help' }}>
      (?)
    </span>
  </label>
)

function Settings() {
  const [form, setForm] = useState({
    playlist_id: '',
    auto_fetch_enabled: false,
    auto_fetch_time: '04:00',
    auto_fetch_window_days: 1,
    spotify_include_groups: 'album,single',
    spotify_market: '',
    local_fetch_spacing_ms: 120,
    release_workers: 10,
    worker_idle_seconds: 20,
    worker_processed_sleep_seconds: 10,
    worker_backend_retry_seconds: 15,
    worker_album_audio_only_strict: true,
    spotify_client_id: '',
    spotify_client_secret: '',
    spotify_oauth_client_id: '',
    spotify_oauth_redirect_uri: '',
    reverse_spotify_playlist_id: '',
    reverse_poll_seconds: 300,
    reverse_liked_limit: 100,
    reverse_spotify_redirect_uri: 'http://localhost:8080/callback',
    reverse_spotify_add_to_playlist: true,
    reverse_spotiflac_enabled: false,
    reverse_spotiflac_output_dir: '/data/downloads',
    reverse_spotiflac_command_template: 'spotiflac "{spotify_url}" "{output_dir}"',
    reverse_spotiflac_timeout_seconds: 600,
    reverse_spotiflac_loop_minutes: 0,
    reverse_track_spacing_ms: 0,
  })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [infoMessage, setInfoMessage] = useState('')
  const [lastAutoFetchDate, setLastAutoFetchDate] = useState('')
  const [importingArtistsJson, setImportingArtistsJson] = useState(false)
  const [importingAuthJson, setImportingAuthJson] = useState(false)
  const [validatingAuthJson, setValidatingAuthJson] = useState(false)
  const [importingSettingsJson, setImportingSettingsJson] = useState(false)
  const [reverseSpotifyResponseUrl, setReverseSpotifyResponseUrl] = useState('')
  const [completingReverseOAuth, setCompletingReverseOAuth] = useState(false)

  const selectedIncludeGroups = String(form.spotify_include_groups || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
  const [currentHour = '04', currentMinute = '00'] = String(form.auto_fetch_time || '04:00').split(':')

  const toggleIncludeGroup = (group) => {
    const current = new Set(selectedIncludeGroups)
    if (current.has(group)) {
      current.delete(group)
    } else {
      current.add(group)
    }
    const nextValue = SPOTIFY_GROUP_OPTIONS.filter((item) => current.has(item)).join(',')
    setForm((prev) => ({ ...prev, spotify_include_groups: nextValue }))
  }

  const setAutoFetchTimePart = (part, value) => {
    const [hour = '04', minute = '00'] = String(form.auto_fetch_time || '04:00').split(':')
    const nextHour = part === 'hour' ? value : hour
    const nextMinute = part === 'minute' ? value : minute
    setForm((prev) => ({ ...prev, auto_fetch_time: `${nextHour}:${nextMinute}` }))
  }

  useEffect(() => {
    async function load() {
      setLoading(true)
      setError('')
      try {
        const settings = await getSettings()
        setForm({
          playlist_id: settings.playlist_id || '',
          auto_fetch_enabled: Boolean(settings.auto_fetch_enabled),
          auto_fetch_time: settings.auto_fetch_time || '04:00',
          auto_fetch_window_days: Number(settings.auto_fetch_window_days || 1),
          spotify_include_groups: settings.spotify_include_groups || 'album,single',
          spotify_market: settings.spotify_market || '',
          local_fetch_spacing_ms: Number(settings.local_fetch_spacing_ms || 120),
          release_workers: Number(settings.release_workers || 10),
          worker_idle_seconds: Number(settings.worker_idle_seconds || 20),
          worker_processed_sleep_seconds: Number(settings.worker_processed_sleep_seconds || 10),
          worker_backend_retry_seconds: Number(settings.worker_backend_retry_seconds || 15),
          worker_album_audio_only_strict:
            settings.worker_album_audio_only_strict === undefined
              ? true
              : Boolean(settings.worker_album_audio_only_strict),
          spotify_client_id: settings.spotify_client_id || '',
          spotify_client_secret: settings.spotify_client_secret || '',
          spotify_oauth_client_id: settings.spotify_oauth_client_id || '',
          spotify_oauth_redirect_uri: settings.spotify_oauth_redirect_uri || '',
          reverse_spotify_playlist_id: settings.reverse_spotify_playlist_id || '',
          reverse_poll_seconds: Number(settings.reverse_poll_seconds || 300),
          reverse_liked_limit: Number(settings.reverse_liked_limit || 100),
          reverse_spotify_redirect_uri:
            settings.reverse_spotify_redirect_uri || 'http://localhost:8080/callback',
          reverse_spotify_add_to_playlist:
            settings.reverse_spotify_add_to_playlist === undefined
              ? true
              : Boolean(settings.reverse_spotify_add_to_playlist),
          reverse_spotiflac_enabled: Boolean(settings.reverse_spotiflac_enabled),
          reverse_spotiflac_output_dir: settings.reverse_spotiflac_output_dir || '/data/downloads',
          reverse_spotiflac_command_template:
            settings.reverse_spotiflac_command_template ||
            'spotiflac "{spotify_url}" "{output_dir}"',
          reverse_spotiflac_timeout_seconds: Number(settings.reverse_spotiflac_timeout_seconds || 600),
          reverse_spotiflac_loop_minutes: Number(settings.reverse_spotiflac_loop_minutes || 0),
          reverse_track_spacing_ms: Number(settings.reverse_track_spacing_ms || 0),
        })
        setLastAutoFetchDate(settings.last_auto_fetch_date || '')
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
    if (!selectedIncludeGroups.length) {
      setError('Seleciona pelo menos um Spotify include group.')
      return
    }
    setSaving(true)
    setError('')
    setInfoMessage('')
    try {
      const saved = await updateSettings({
        playlist_id: form.playlist_id,
        auto_fetch_enabled: form.auto_fetch_enabled,
        auto_fetch_time: form.auto_fetch_time,
        auto_fetch_window_days: Number(form.auto_fetch_window_days || 1),
        spotify_include_groups: form.spotify_include_groups,
        spotify_market: form.spotify_market,
        local_fetch_spacing_ms: Number(form.local_fetch_spacing_ms || 0),
        release_workers: Number(form.release_workers || 1),
        worker_idle_seconds: Number(form.worker_idle_seconds || 20),
        worker_processed_sleep_seconds: Number(form.worker_processed_sleep_seconds || 10),
        worker_backend_retry_seconds: Number(form.worker_backend_retry_seconds || 15),
        worker_album_audio_only_strict: Boolean(form.worker_album_audio_only_strict),
        spotify_client_id: form.spotify_client_id,
        spotify_client_secret: form.spotify_client_secret,
        spotify_oauth_client_id: form.spotify_oauth_client_id,
        spotify_oauth_redirect_uri: form.spotify_oauth_redirect_uri,
        reverse_spotify_playlist_id: form.reverse_spotify_playlist_id,
        reverse_poll_seconds: Number(form.reverse_poll_seconds || 300),
        reverse_liked_limit: Number(form.reverse_liked_limit || 100),
        reverse_spotify_redirect_uri: form.reverse_spotify_redirect_uri,
        reverse_spotify_add_to_playlist: Boolean(form.reverse_spotify_add_to_playlist),
        reverse_spotiflac_enabled: Boolean(form.reverse_spotiflac_enabled),
        reverse_spotiflac_output_dir: form.reverse_spotiflac_output_dir,
        reverse_spotiflac_command_template: form.reverse_spotiflac_command_template,
        reverse_spotiflac_timeout_seconds: Number(form.reverse_spotiflac_timeout_seconds || 600),
        reverse_spotiflac_loop_minutes: Number(form.reverse_spotiflac_loop_minutes || 0),
        reverse_track_spacing_ms: Number(form.reverse_track_spacing_ms || 0),
      })
      setInfoMessage('Settings guardadas com sucesso.')
      setLastAutoFetchDate(saved.last_auto_fetch_date || '')
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
      setForm((previous) => ({
        ...previous,
        playlist_id: saved.playlist_id || '',
        auto_fetch_enabled: Boolean(saved.auto_fetch_enabled),
        auto_fetch_time: saved.auto_fetch_time || '04:00',
        auto_fetch_window_days: Number(saved.auto_fetch_window_days || 1),
        spotify_include_groups: saved.spotify_include_groups || 'album,single',
        spotify_market: saved.spotify_market || '',
        local_fetch_spacing_ms: Number(saved.local_fetch_spacing_ms || 120),
        release_workers: Number(saved.release_workers || 10),
        worker_idle_seconds: Number(saved.worker_idle_seconds || 20),
        worker_processed_sleep_seconds: Number(saved.worker_processed_sleep_seconds || 10),
        worker_backend_retry_seconds: Number(saved.worker_backend_retry_seconds || 15),
        worker_album_audio_only_strict:
          saved.worker_album_audio_only_strict === undefined
            ? true
            : Boolean(saved.worker_album_audio_only_strict),
        spotify_client_id: saved.spotify_client_id || '',
        spotify_client_secret: saved.spotify_client_secret || '',
        spotify_oauth_client_id: saved.spotify_oauth_client_id || '',
        spotify_oauth_redirect_uri: saved.spotify_oauth_redirect_uri || '',
        reverse_spotify_playlist_id: saved.reverse_spotify_playlist_id || '',
        reverse_poll_seconds: Number(saved.reverse_poll_seconds || 300),
        reverse_liked_limit: Number(saved.reverse_liked_limit || 100),
        reverse_spotify_redirect_uri: saved.reverse_spotify_redirect_uri || 'http://localhost:8080/callback',
        reverse_spotify_add_to_playlist:
          saved.reverse_spotify_add_to_playlist === undefined
            ? true
            : Boolean(saved.reverse_spotify_add_to_playlist),
        reverse_spotiflac_enabled: Boolean(saved.reverse_spotiflac_enabled),
        reverse_spotiflac_output_dir: saved.reverse_spotiflac_output_dir || '/data/downloads',
        reverse_spotiflac_command_template:
          saved.reverse_spotiflac_command_template ||
          'spotiflac "{spotify_url}" "{output_dir}"',
        reverse_spotiflac_timeout_seconds: Number(saved.reverse_spotiflac_timeout_seconds || 600),
        reverse_spotiflac_loop_minutes: Number(saved.reverse_spotiflac_loop_minutes || 0),
        reverse_track_spacing_ms: Number(saved.reverse_track_spacing_ms || 0),
      }))
      setLastAutoFetchDate(saved.last_auto_fetch_date || '')
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

  const onCompleteReverseOAuth = async () => {
    if (!reverseSpotifyResponseUrl.trim()) {
      setError('Cola primeiro o response URL devolvido pelo Spotify.')
      return
    }
    setCompletingReverseOAuth(true)
    setError('')
    setInfoMessage('')
    try {
      await completeReverseSpotifyOAuth(reverseSpotifyResponseUrl.trim())
      setInfoMessage('OAuth reverse concluido. Token guardado com sucesso.')
      setReverseSpotifyResponseUrl('')
    } catch (err) {
      setError(err.message)
    } finally {
      setCompletingReverseOAuth(false)
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
            <h3 className="title is-6 has-text-light mb-3">Credenciais e Integracoes Spotify</h3>
            <div className="columns is-multiline mb-1">
              <div className="column is-8-desktop is-12-tablet">
                <div className="field mb-0">
                  <HelpLabel
                    text="Playlist ID do YouTube Music"
                    help="Playlist de destino usada pelo worker principal para adicionar releases."
                  />
                  <Input
                    value={form.playlist_id}
                    onChange={(event) => setForm((prev) => ({ ...prev, playlist_id: event.target.value }))}
                    placeholder="Ex: PLxxxxxxxxxxxxxxxxxxxx"
                  />
                </div>
              </div>
              <div className="column is-4-desktop is-12-tablet">
                <div className="field mb-0">
                  <HelpLabel
                    text="Spotify market (opcional)"
                    help="Pais/codigo ISO para filtrar resultados da API Spotify (ex.: PT, BR, US)."
                  />
                  <div className="select is-fullwidth">
                    <select
                      value={form.spotify_market}
                      onChange={(event) => setForm((prev) => ({ ...prev, spotify_market: event.target.value }))}
                    >
                      {SPOTIFY_MARKET_OPTIONS.map((market) => (
                        <option key={market || 'none'} value={market}>
                          {market || 'Sem market fixo'}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>
            </div>

            <div className="columns is-multiline mb-2">
              <div className="column is-6-desktop is-12-tablet">
                <HelpLabel
                  text="Spotify Client ID (backend)"
                  help="Client ID usado pelo backend e worker reverse para chamar APIs Spotify."
                />
                <Input
                  value={form.spotify_client_id}
                  onChange={(event) => setForm((prev) => ({ ...prev, spotify_client_id: event.target.value }))}
                  placeholder="Client ID para API Spotify no backend"
                />
              </div>
              <div className="column is-6-desktop is-12-tablet">
                <HelpLabel
                  text="Spotify Client Secret (backend)"
                  help="Segredo OAuth da app Spotify; nao partilhar."
                />
                <Input
                  value={form.spotify_client_secret}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, spotify_client_secret: event.target.value }))
                  }
                  placeholder="Client Secret para API Spotify no backend"
                />
              </div>
            </div>
            <h3 className="title is-6 has-text-light mb-3 mt-2">Reverse Worker (YT Likes - Spotify)</h3>
            <div className="columns is-multiline mb-2">
              <div className="column is-6-desktop is-12-tablet">
                <HelpLabel
                  text="Reverse worker: Spotify Playlist ID"
                  help="Playlist Spotify onde os likes encontrados sao adicionados (se ativo)."
                />
                <Input
                  value={form.reverse_spotify_playlist_id}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, reverse_spotify_playlist_id: event.target.value }))
                  }
                  placeholder="Playlist destino dos likes do YTMusic"
                />
              </div>
              <div className="column is-6-desktop is-12-tablet">
                <HelpLabel
                  text="Reverse worker: Spotify OAuth Redirect URI"
                  help="URI de callback registado no Spotify Dashboard para concluir OAuth do reverse worker."
                />
                <Input
                  value={form.reverse_spotify_redirect_uri}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, reverse_spotify_redirect_uri: event.target.value }))
                  }
                  placeholder="Ex: http://localhost:8080/callback"
                />
              </div>
            </div>
            <div className="columns is-multiline mb-2">
              <div className="column is-3-desktop is-6-tablet">
                <HelpLabel
                  text="Reverse poll (s)"
                  help="Intervalo entre ciclos do reverse worker (leitura de likes e processamento)."
                />
                <Input
                  type="number"
                  min="30"
                  max="86400"
                  value={form.reverse_poll_seconds}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, reverse_poll_seconds: Number(event.target.value || 300) }))
                  }
                />
              </div>
              <div className="column is-3-desktop is-6-tablet">
                <HelpLabel
                  text="Reverse liked limit"
                  help="Numero maximo de likes lidos por ciclo no YouTube Music."
                />
                <Input
                  type="number"
                  min="1"
                  max="5000"
                  value={form.reverse_liked_limit}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, reverse_liked_limit: Number(event.target.value || 100) }))
                  }
                />
              </div>
              <div className="column is-3-desktop is-6-tablet">
                <HelpLabel
                  text="Spotiflac timeout (s)"
                  help="Tempo maximo por execucao de download antes de marcar erro."
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
              <div className="column is-3-desktop is-6-tablet">
                <HelpLabel
                  text="Spotiflac loop (min)"
                  help="0 = uma execucao por ciclo do worker; >0 deixa o spotiflac em loop interno."
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
            </div>
            <div className="columns is-multiline mb-2">
              <div className="column is-3-desktop is-6-tablet">
                <HelpLabel
                  text="Delay entre tracks reverse (ms)"
                  help="Pausa entre tracks no reverse worker para reduzir rate-limit e sobrecarga."
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
            </div>
            <p className="has-text-grey is-size-7 mb-2">
              Spotiflac loop em <code>0</code> = single run por ciclo do worker. Usa delay entre tracks para reduzir
              risco de rate-limit.
            </p>
            <div className="field mb-2">
              <label className="checkbox has-text-light">
                <input
                  type="checkbox"
                  checked={form.reverse_spotify_add_to_playlist}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, reverse_spotify_add_to_playlist: event.target.checked }))
                  }
                />{' '}
                Reverse worker: adicionar tambem na playlist do Spotify
              </label>
              <p className="has-text-grey is-size-7 mt-1">
                Se desativado, o reverse so trata downloads/historico e nao mexe em playlists Spotify.
              </p>
            </div>
            <div className="field mb-2">
              <label className="checkbox has-text-light">
                <input
                  type="checkbox"
                  checked={form.reverse_spotiflac_enabled}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, reverse_spotiflac_enabled: event.target.checked }))
                  }
                />{' '}
                Ativar download via Spotiflac
              </label>
              <p className="has-text-grey is-size-7 mt-1">
                Quando ativo, so marca como processado apos download valido.
              </p>
            </div>
            <h3 className="title is-6 has-text-light mb-3 mt-2">Spotiflac</h3>
            <div className="columns is-multiline mb-2">
              <div className="column is-5-desktop is-12-tablet">
                <HelpLabel
                  text="Spotiflac output dir"
                  help="Diretorio dentro do container onde os ficheiros sao gravados (deve estar em volume persistente)."
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
                  text="Spotiflac command template"
                  help="Comando CLI alternativo; placeholders: {spotify_url}, {output_dir}, {artist}, {title}."
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
              Placeholders suportados no comando: <code>{'{spotify_url}'}</code>, <code>{'{output_dir}'}</code>,{' '}
              <code>{'{artist}'}</code>, <code>{'{title}'}</code>. Erros de download entram em Erros com tipo{' '}
              <code>DOWNLOAD_SPOTIFLAC</code>.
            </p>
            <div className="columns is-multiline mb-4">
              <div className="column is-9-desktop is-12-tablet">
                <HelpLabel
                  text="Reverse OAuth response URL (copiar/colar)"
                  help="URL final do callback Spotify com ?code=... para guardar token sem modo interativo."
                />
                <Input
                  value={reverseSpotifyResponseUrl}
                  onChange={(event) => setReverseSpotifyResponseUrl(event.target.value)}
                  placeholder="http://127.0.0.1:8080/callback?code=..."
                />
                <p className="has-text-grey is-size-7 mt-2">
                  Depois de autorizar no Spotify, cola aqui o URL completo e clica em concluir.
                </p>
              </div>
              <div className="column is-3-desktop is-12-tablet is-flex is-align-items-flex-end">
                <Button
                  type="button"
                  primary
                  disabled={completingReverseOAuth || loading}
                  onClick={onCompleteReverseOAuth}
                >
                  {completingReverseOAuth ? 'A concluir...' : 'Concluir OAuth reverse'}
                </Button>
              </div>
            </div>
            <p className="has-text-grey is-size-7 mb-4">
              Estes campos controlam o worker_reverse (likes no YTMusic para playlist privada no Spotify).
            </p>

            <h3 className="title is-6 has-text-light mb-3 mt-2">OAuth Frontend (Importar artistas)</h3>
            <div className="columns is-multiline mb-2">
              <div className="column is-6-desktop is-12-tablet">
                <HelpLabel
                  text="Spotify OAuth Client ID (frontend)"
                  help="Client ID usado no browser para login do utilizador e import de artistas seguidos."
                />
                <Input
                  value={form.spotify_oauth_client_id}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, spotify_oauth_client_id: event.target.value }))
                  }
                  placeholder="Client ID para importar artistas seguidos"
                />
              </div>
              <div className="column is-6-desktop is-12-tablet">
                <HelpLabel
                  text="Spotify OAuth Redirect URI"
                  help="Callback do frontend registado na app Spotify (ex.: http://SEU_IP:3001/artists)."
                />
                <Input
                  value={form.spotify_oauth_redirect_uri}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, spotify_oauth_redirect_uri: event.target.value }))
                  }
                  placeholder="Ex: http://SEU_IP:3001/artists"
                />
              </div>
            </div>

            <div className="field mb-4">
              <label className="checkbox has-text-light">
                <input
                  type="checkbox"
                  checked={form.auto_fetch_enabled}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, auto_fetch_enabled: event.target.checked }))
                  }
                />{' '}
                Ativar fetch automatico diario
              </label>
              <p className="has-text-grey is-size-7 mt-1">
                O backend cria automaticamente jobs diarios de fetch de releases conforme hora/janela.
              </p>
            </div>

            <div className="columns is-multiline mb-4">
              <div className="column is-6-desktop is-12-tablet">
                <label className="label has-text-light">Importar JSON de artistas</label>
                <input type="file" accept=".json,application/json" onChange={onImportArtistsJson} />
                {importingArtistsJson && <p className="has-text-grey is-size-7 mt-1">A importar artistas...</p>}
              </div>
              <div className="column is-6-desktop is-12-tablet">
                <label className="label has-text-light">Importar JSON de auth YTMusic</label>
                <input type="file" accept=".json,application/json" onChange={onImportYTMusicAuthJson} />
                {importingAuthJson && <p className="has-text-grey is-size-7 mt-1">A importar auth...</p>}
                <div className="mt-2">
                  <Button
                    type="button"
                    onClick={onValidateYTMusicAuth}
                    disabled={validatingAuthJson || loading}
                  >
                    {validatingAuthJson ? 'A validar auth...' : 'Validar auth YTMusic'}
                  </Button>
                </div>
              </div>
              <div className="column is-6-desktop is-12-tablet">
                <label className="label has-text-light">Importar JSON de settings</label>
                <input type="file" accept=".json,application/json" onChange={onImportSettingsJson} />
                {importingSettingsJson && <p className="has-text-grey is-size-7 mt-1">A importar settings...</p>}
              </div>
            </div>

            <div className="columns is-multiline mb-2">
              <div className="column is-3-desktop is-6-tablet">
                <HelpLabel
                  text="Hora diaria (UTC)"
                  help="Horario do fetch automatico; usa fuso UTC."
                />
                <div className="columns is-mobile">
                  <div className="column pr-1">
                    <div className="select is-fullwidth">
                      <select value={currentHour} onChange={(event) => setAutoFetchTimePart('hour', event.target.value)}>
                        {HOUR_OPTIONS.map((hour) => (
                          <option key={hour} value={hour}>
                            {hour}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                  <div className="column pl-1">
                    <div className="select is-fullwidth">
                      <select
                        value={MINUTE_OPTIONS.includes(currentMinute) ? currentMinute : '00'}
                        onChange={(event) => setAutoFetchTimePart('minute', event.target.value)}
                      >
                        {MINUTE_OPTIONS.map((minute) => (
                          <option key={minute} value={minute}>
                            {minute}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                </div>
              </div>
              <div className="column is-3-desktop is-6-tablet">
                <HelpLabel
                  text="Janela (dias para tras)"
                  help="Dias para tras usados no fetch automatico (ex.: 1 = ontem/hoje)."
                />
                <Input
                  type="number"
                  min="1"
                  max="30"
                  value={form.auto_fetch_window_days}
                  onChange={(event) =>
                    setForm((prev) => ({
                      ...prev,
                      auto_fetch_window_days: Number(event.target.value || 1),
                    }))
                  }
                />
              </div>
              <div className="column is-6-desktop is-12-tablet">
                <HelpLabel
                  text="Spotify include groups"
                  help="Tipos de lancamento considerados na procura de releases."
                />
                <div className="is-flex is-flex-wrap-wrap" style={{ gap: '0.75rem' }}>
                  {SPOTIFY_GROUP_OPTIONS.map((group) => (
                    <label className="checkbox has-text-light" key={group}>
                      <input
                        type="checkbox"
                        checked={selectedIncludeGroups.includes(group)}
                        onChange={() => toggleIncludeGroup(group)}
                      />{' '}
                      {group}
                    </label>
                  ))}
                </div>
                <p className="has-text-grey is-size-7 mt-2">
                  Recomendado para menos rate-limit: <code>album</code> e <code>single</code>.
                </p>
              </div>
            </div>
            <h3 className="title is-6 has-text-light mb-3 mt-2">Performance e Ritmos de Worker</h3>

            <div className="columns is-multiline mb-2">
              <div className="column is-4-desktop is-12-tablet">
                <HelpLabel
                  text="Delay entre artistas (ms)"
                  help="Pausa no fetch local entre artistas para reduzir 429 da API Spotify."
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
                  text="Workers para /releases"
                  help="Numero de workers paralelos no fetch de releases (mais alto = mais rapido/mais risco 429)."
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
              <div className="column is-4-desktop is-6-tablet">
                <HelpLabel
                  text="Worker retry backend (s)"
                  help="Tempo de espera quando o worker principal falha a comunicar com backend."
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
            </div>
            <p className="has-text-grey is-size-7 mb-4">
              Mais delay e menos workers reduzem 429; mais workers podem acelerar, mas com maior risco de rate-limit.
            </p>

            <div className="columns is-multiline mb-2">
              <div className="column is-6-desktop is-12-tablet">
                <HelpLabel
                  text="Worker idle (s)"
                  help="Tempo de espera quando a fila csv_releases nao tem itens."
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
              <div className="column is-6-desktop is-12-tablet">
                <HelpLabel
                  text="Worker pos-processamento (s)"
                  help="Pausa apos processar itens antes de verificar novamente a fila."
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
            </div>

            <div className="field mb-4">
              <label className="checkbox has-text-light">
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
                Worker album audio-only strict mode
              </label>
              <p className="has-text-grey is-size-7 mt-2">
                Se ativo, evita videos musicais em albuns e tenta fallback por faixa.
              </p>
            </div>

            {lastAutoFetchDate && (
              <p className="has-text-grey mb-3">Ultimo fetch automatico: {lastAutoFetchDate}</p>
            )}
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
