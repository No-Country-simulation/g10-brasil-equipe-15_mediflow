import { NavLink } from 'react-router'
import { cx } from '../../lib/cx'
import { Icon } from '../ui'
import type { IconName } from '../ui'

type NavItemProps = {
  to: string
  label: string
  icon: IconName
}

export function NavItem({ to, label, icon }: NavItemProps) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        cx(
          'flex h-11 items-center gap-3 rounded-sm px-3 text-base font-medium transition-colors',
          'focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-primary',
          isActive
            ? 'bg-sidebar-active text-sidebar-text-strong'
            : 'text-sidebar-text hover:bg-sidebar-active/60 hover:text-sidebar-text-strong',
        )
      }
    >
      <Icon name={icon} size={20} />
      {label}
    </NavLink>
  )
}
