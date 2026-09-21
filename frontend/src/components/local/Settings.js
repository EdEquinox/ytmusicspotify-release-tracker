import { useEffect, useState } from 'react'
import { Button, Content, Header, HeaderNav, Input, VerticalLayout } from 'components/common'
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

/** @param {Record<string, unknown>} settings */
function mapSettingsToForm(settings) {
  return {
    playlist_id: settings.playlist_id || '',
    ytmusic_user: settings.ytmusic_user || '',
    local_fetch_spacing_ms: Number(settings.local_fetch_spacing_ms || 120),
    release_workers: Number(settings.release_workers || 10),
    worker_idle_seconds: Number(settings.worker_idle_seconds || 20),
    worker_processed_sleep_seconds: Number(settings.worker_processed_sleep_seconds || 10),
    worker_backend_retry_seconds: Number(settings.worker_backend_retry_seconds || 15),
    worker_album_audio_only_strict:
      settings.worker_album_audio_only_strict === undefined
        ? true
        : Boolean(settings.worker_album_audio_only_strict),
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
        playlist_id: form.playlist_id,
        ytmusic_user: form.ytmusic_user,
        local_fetch_spacing_ms: Number(form.local_fetch_spacing_ms || 0),
        release_workers: Number(form.release_workers || 1),
        worker_idle_seconds: Number(form.worker_idle_seconds || 20),
        worker_processed_sleep_seconds: Number(form.worker_processed_sleep_seconds || 10),
        worker_backend_retry_seconds: Number(form.worker_backend_retry_seconds || 15),
        worker_album_audio_only_strict: Boolean(form.worker_album_audio_only_strict),
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
      <Header>
        <HeaderNav />
      </Header>
      <Content>
        <div className="LocalPage">
          <form className="LocalPanel" onSubmit={onSubmit}>
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
            <div className="field mb-5">
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

            <h3 className="title is-6 has-text-light mb-3">Importar dados (JSON)</h3>
            <div className="columns is-multiline mb-5">
              <div className="column is-6-desktop is-12-tablet">
                <label className="label has-text-light">Artistas</label>
                <input type="file" accept=".json,application/json" onChange={onImportArtistsJson} />
                {importingArtistsJson && <p className="has-text-grey is-size-7 mt-1">A importar artistas...</p>}
              </div>
              <div className="column is-6-desktop is-12-tablet">
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
            </div>

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
