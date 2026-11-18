import type { HTMLAttributes } from 'react'
import { cx } from '../../lib/cx'

export type BadgeTone = 'neutral' | 'success' | 'danger' | 'warning' | 'info' | 'error'

type BadgeProps = HTMLAttributes<HTMLSpanElement> & {
  tone?: BadgeTone
  size?: 'S' | 'L'
}

const tones: Record<BadgeTone, string> = {
  neutral: 'bg-status-neutral-bg text-status-neutral-fg',
  success: 'bg-status-success-bg text-status-success-fg',
  danger: 'bg-status-danger-bg text-status-danger-fg',
  warning: 'bg-status-warning-bg text-status-warning-fg',
  info: 'bg-status-info-bg text-status-info-fg',
  // Borda desenhada por dentro (ring inset) para não aumentar a altura do badge.
  error: 'bg-status-error-bg text-status-error-fg ring-1 ring-inset ring-status-error-border',
}

export function Badge({ tone = 'neutral', size = 'S', className, ...props }: BadgeProps) {
  return (
    <span
      className={cx(
        'inline-flex items-center justify-center whitespace-nowrap rounded-full px-2.5 font-semibold leading-none',
        size === 'S' ? 'py-1 text-xs' : 'py-1.25 text-caption',
        tones[tone],
        className,
      )}
      {...props}
    />
  )
}
