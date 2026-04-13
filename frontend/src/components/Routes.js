import { Route, Routes as RouterRoutes } from 'react-router-dom'
import { Auth, App } from 'components'
import { Releases } from 'components/releases'
import ManageArtists from 'components/local/ManageArtists'
import SyncErrors from 'components/local/SyncErrors'
import Settings from 'components/local/Settings'
import SetupGuide from 'components/local/SetupGuide'

function Routes() {
  return (
    <RouterRoutes>
      <Route path="/" element={<App />}>
        <Route index element={<Releases />} />
        <Route path="artists" element={<ManageArtists />} />
        <Route path="errors" element={<SyncErrors />} />
        <Route path="settings" element={<Settings />} />
        <Route path="setup" element={<SetupGuide />} />
      </Route>
      <Route path="auth" element={<Auth />} />
    </RouterRoutes>
  )
}

export default Routes
