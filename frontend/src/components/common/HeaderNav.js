import { useMatch } from 'react-router-dom'
import classNames from 'classnames'
import ButtonLink from './ButtonLink'

/** @type {{ to: string, match?: string, end?: boolean, label: string, icon: string }[]} */
const TABS = [
  { to: '/', match: '/', end: true, label: 'Releases', icon: 'fas fa-music' },
  { to: '/artists', label: 'Artistas', icon: 'fas fa-users' },
  { to: '/errors', label: 'Erros', icon: 'fas fa-triangle-exclamation' },
  { to: '/history', label: 'Historico', icon: 'fas fa-clock-rotate-left' },
  { to: '/settings', label: 'Settings', icon: 'fas fa-gear' },
  { to: '/setup', label: 'Guia', icon: 'fas fa-circle-info' },
]

/**
 * @param {{
 *   to: string
 *   match?: string
 *   end?: boolean
 *   label: string
 *   icon: string
 * }} props
 */
function HeaderNavTab({ to, match, end, label, icon }) {
  const active = Boolean(useMatch({ path: match || to, end: end ?? true }))

  return (
    <ButtonLink
      to={to}
      match={match || to}
      icon={icon}
      titleOnly={label}
      className={classNames('HeaderNav__tab', { 'HeaderNav__tab--active': active })}
      activeClass="HeaderNav__tab--active"
    >
      {active ? label : null}
    </ButtonLink>
  )
}

/** Header navigation tabs: only the active tab shows its label. */
function HeaderNav() {
  return (
    <div className="Header__right HeaderNav" role="tablist" aria-label="Navegacao">
      {TABS.map((tab) => (
        <HeaderNavTab key={tab.to} {...tab} />
      ))}
    </div>
  )
}

export default HeaderNav
