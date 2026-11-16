import type { InputHTMLAttributes } from 'react'
import { cx } from '../../lib/cx'

type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  /** Fonte monoespaçada (usada no ID do documento). */
  mono?: boolean
}

export function Input({ mono = true, className, ...props }: InputProps) {
  return (
    <input
      className={cx(
        'h-11 w-full rounded-md border border-border-input bg-surface px-3 leading-none text-text',
        'placeholder:text-text-placeholder',
        'focus-visible:border-primary focus-visible:outline-2 focus-visible:-outline-offset-1 focus-visible:outline-primary',
        mono ? 'font-mono text-sm' : 'text-[15px]',
        className,
      )}
      {...props}
    />
  )
}
