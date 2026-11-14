import type { ComponentType, SVGProps } from 'react'
import Alert from '../../assets/icons/alert.svg?react'
import ArrowRight from '../../assets/icons/arrow-right.svg?react'
import Back from '../../assets/icons/back.svg?react'
import Check from '../../assets/icons/check.svg?react'
import ChevronDown from '../../assets/icons/chevron-down.svg?react'
import Code from '../../assets/icons/code.svg?react'
import Copy from '../../assets/icons/copy.svg?react'
import Doc from '../../assets/icons/doc.svg?react'
import Eye from '../../assets/icons/eye.svg?react'
import Info from '../../assets/icons/info.svg?react'
import List from '../../assets/icons/list.svg?react'
import Lock from '../../assets/icons/lock.svg?react'
import LogoMarca from '../../assets/icons/logo-marca.svg?react'
import Logout from '../../assets/icons/logout.svg?react'
import Plus from '../../assets/icons/plus.svg?react'
import Search from '../../assets/icons/search.svg?react'
import Shield from '../../assets/icons/shield.svg?react'
import Upload from '../../assets/icons/upload.svg?react'

const icons = {
  alert: Alert,
  'arrow-right': ArrowRight,
  back: Back,
  check: Check,
  'chevron-down': ChevronDown,
  code: Code,
  copy: Copy,
  doc: Doc,
  eye: Eye,
  info: Info,
  list: List,
  lock: Lock,
  'logo-marca': LogoMarca,
  logout: Logout,
  plus: Plus,
  search: Search,
  shield: Shield,
  upload: Upload,
} satisfies Record<string, ComponentType<SVGProps<SVGSVGElement>>>

export type IconName = keyof typeof icons

type IconProps = Omit<SVGProps<SVGSVGElement>, 'name'> & {
  name: IconName
  /** Tamanho em px (sobrescreve o tamanho original do Figma). */
  size?: number
  /** Texto acessível. Sem ele o ícone é decorativo (aria-hidden). */
  title?: string
}

/** Ícones da Biblioteca do Figma. Herdam a cor do texto via currentColor (exceto `logo-marca`). */
export function Icon({ name, size, title, ...props }: IconProps) {
  const Component = icons[name]
  const a11y = title ? { role: 'img', 'aria-label': title } : { 'aria-hidden': true }

  return (
    <Component
      {...(size ? { width: size, height: size } : {})}
      {...a11y}
      {...props}
    />
  )
}
