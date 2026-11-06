import type { SelectHTMLAttributes } from 'react'
import { cx } from '../../lib/cx'
import { Icon } from './Icon'

type SelectProps = SelectHTMLAttributes<HTMLSelectElement>

/** Select nativo com chevron do Figma (o select continua acessível por teclado e leitor de tela). */
export function Select({ className, children, ...props }: SelectProps) {
  return (
    <div className="relative">
      <select
        className={cx(
          'h-11 w-full appearance-none rounded-md border border-border-input bg-surface pr-9 pl-3',
          'text-[15px] leading-none text-text',
          'focus-visible:border-primary focus-visible:outline-2 focus-visible:-outline-offset-1 focus-visible:outline-primary',
          className,
        )}
        {...props}
      >
        {children}
      </select>
      <Icon
        name="chevron-down"
        size={16}
        className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-text"
      />
    </div>
  )
}
