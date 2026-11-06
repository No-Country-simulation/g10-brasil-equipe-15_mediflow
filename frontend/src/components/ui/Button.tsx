import type { ButtonHTMLAttributes } from 'react'
import { cx } from '../../lib/cx'
import { Icon } from './Icon'

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  /** `primary` = botão principal do formulário; `secondary` = botão com borda. */
  variant?: 'primary' | 'secondary'
  /** Só vale para `secondary` (M = 48px, S = 36px). */
  size?: 'M' | 'S'
  /** Só vale para `primary`: exibe a seta à direita do texto. */
  withIcon?: boolean
}

const base =
  'inline-flex items-center justify-center font-semibold leading-none transition-colors ' +
  'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary'

export function Button({
  variant = 'primary',
  size = 'M',
  withIcon = false,
  className,
  type = 'button',
  children,
  ...props
}: ButtonProps) {
  if (variant === 'secondary') {
    return (
      <button
        type={type}
        className={cx(
          base,
          'border border-border-input bg-surface font-medium text-text leading-normal',
          'hover:bg-subtle disabled:cursor-not-allowed disabled:opacity-60',
          size === 'M' ? 'h-12 rounded-md px-4.5 text-base' : 'h-9 rounded-sm px-3 text-sm',
          className,
        )}
        {...props}
      >
        {children}
      </button>
    )
  }

  return (
    <button
      type={type}
      className={cx(
        base,
        'h-12 gap-2.5 rounded-md px-5.5 text-base',
        'bg-primary text-on-primary hover:bg-primary-hover',
        'disabled:cursor-not-allowed disabled:bg-disabled disabled:text-text-secondary',
        className,
      )}
      {...props}
    >
      {children}
      {withIcon && <Icon name="arrow-right" size={18} />}
    </button>
  )
}
