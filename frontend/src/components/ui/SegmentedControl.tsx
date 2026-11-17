import { cx } from '../../lib/cx'

type Option<T extends string> = { value: T; label: string }

type SegmentedControlProps<T extends string> = {
  options: ReadonlyArray<Option<T>>
  value: T
  onChange: (value: T) => void
  'aria-label': string
}

export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  'aria-label': ariaLabel,
}: SegmentedControlProps<T>) {
  return (
    <div role="group" aria-label={ariaLabel} className="inline-flex gap-1 rounded-md bg-muted p-1">
      {options.map((option) => {
        const selected = option.value === value
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={selected}
            onClick={() => onChange(option.value)}
            className={cx(
              'h-10 rounded-sm px-4.5 text-sm leading-none font-semibold transition-colors',
              'focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-primary',
              selected ? 'bg-surface text-text shadow-xs' : 'text-text-secondary hover:text-text',
            )}
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )
}
