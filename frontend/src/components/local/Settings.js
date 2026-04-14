import { useEffect, useState } from 'react'
import { Button, ButtonLink, Content, Header, Input, VerticalLayout } from 'components/common'
import {
  completeReverseSpotifyOAuth,
  getSettings,
  importArtists,
  importYTMusicAuth,
  updateSettings,
} from 'backendApi'

const SPOTIFY_GROUP_OPTIONS = ['album', 'single', 'compilation', 'appears_on']
const SPOTIFY_MARKET_OPTIONS = ['', 'PT', 'BR', 'US', 'GB', 'ES', 'FR', 'DE', 'IT', 'JP']
const HOUR_OPTIONS = Array.from({ length: 24 }, (_, idx) => String(idx).padStart(2, '0'))
const MINUTE_OPTIONS = Array.from({ length: 12 }, (_, idx) => String(idx * 5).padStart(2, '0'))

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
  })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [infoMessage, setInfoMessage] = useState('')
  const [lastAutoFetchDate, setLastAutoFetchDate] = useState('')
  const [importingArtistsJson, setImportingArtistsJson] = useState(false)
  const [importingAuthJson, setImportingAuthJson] = useState(false)
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
      await importYTMusicAuth(parsed)
      setInfoMessage('Auth do YTMusic importada com sucesso.')
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
            <div className="columns is-multiline mb-1">
              <div className="column is-8-desktop is-12-tablet">
                <div className="field mb-0">
                  <label className="label has-text-light">Playlist ID do YouTube Music</label>
                  <Input
                    value={form.playlist_id}
                    onChange={(event) => setForm((prev) => ({ ...prev, playlist_id: event.target.value }))}
                    placeholder="Ex: PLxxxxxxxxxxxxxxxxxxxx"
                  />
                </div>
              </div>
              <div className="column is-4-desktop is-12-tablet">
                <div className="field mb-0">
                  <label className="label has-text-light">Spotify market (opcional)</label>
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
                <label className="label has-text-light">Spotify Client ID (backend)</label>
                <Input
                  value={form.spotify_client_id}
                  onChange={(event) => setForm((prev) => ({ ...prev, spotify_client_id: event.target.value }))}
                  placeholder="Client ID para API Spotify no backend"
                />
              </div>
              <div className="column is-6-desktop is-12-tablet">
                <label className="label has-text-light">Spotify Client Secret (backend)</label>
                <Input
                  value={form.spotify_client_secret}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, spotify_client_secret: event.target.value }))
                  }
                  placeholder="Client Secret para API Spotify no backend"
                />
              </div>
            </div>
            <div className="columns is-multiline mb-2">
              <div className="column is-6-desktop is-12-tablet">
                <label className="label has-text-light">Reverse worker: Spotify Playlist ID</label>
                <Input
                  value={form.reverse_spotify_playlist_id}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, reverse_spotify_playlist_id: event.target.value }))
                  }
                  placeholder="Playlist destino dos likes do YTMusic"
                />
              </div>
              <div className="column is-6-desktop is-12-tablet">
                <label className="label has-text-light">Reverse worker: Spotify OAuth Redirect URI</label>
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
                <label className="label has-text-light">Reverse poll (s)</label>
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
                <label className="label has-text-light">Reverse liked limit</label>
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
                <label className="label has-text-light">Spotiflac timeout (s)</label>
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
            </div>
            <div className="columns is-multiline mb-2">
              <div className="column is-5-desktop is-12-tablet">
                <label className="label has-text-light">Spotiflac output dir</label>
                <Input
                  value={form.reverse_spotiflac_output_dir}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, reverse_spotiflac_output_dir: event.target.value }))
                  }
                  placeholder="/data/downloads"
                />
              </div>
              <div className="column is-7-desktop is-12-tablet">
                <label className="label has-text-light">Spotiflac command template</label>
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
                <label className="label has-text-light">Reverse OAuth response URL (copiar/colar)</label>
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

            <div className="columns is-multiline mb-2">
              <div className="column is-6-desktop is-12-tablet">
                <label className="label has-text-light">Spotify OAuth Client ID (frontend)</label>
                <Input
                  value={form.spotify_oauth_client_id}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, spotify_oauth_client_id: event.target.value }))
                  }
                  placeholder="Client ID para importar artistas seguidos"
                />
              </div>
              <div className="column is-6-desktop is-12-tablet">
                <label className="label has-text-light">Spotify OAuth Redirect URI</label>
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
              </div>
              <div className="column is-6-desktop is-12-tablet">
                <label className="label has-text-light">Importar JSON de settings</label>
                <input type="file" accept=".json,application/json" onChange={onImportSettingsJson} />
                {importingSettingsJson && <p className="has-text-grey is-size-7 mt-1">A importar settings...</p>}
              </div>
            </div>

            <div className="columns is-multiline mb-2">
              <div className="column is-3-desktop is-6-tablet">
                <label className="label has-text-light">Hora diaria (UTC)</label>
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
                <label className="label has-text-light">Janela (dias para tras)</label>
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
                <label className="label has-text-light">Spotify include groups</label>
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

            <div className="columns is-multiline mb-2">
              <div className="column is-4-desktop is-12-tablet">
                <label className="label has-text-light">Delay entre artistas (ms)</label>
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
                <label className="label has-text-light">Workers para /releases</label>
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
                <label className="label has-text-light">Worker retry backend (s)</label>
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
                <label className="label has-text-light">Worker idle (s)</label>
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
                <label className="label has-text-light">Worker pos-processamento (s)</label>
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
