import type { ReactNode } from 'react'

type FieldProps = {
  label: string
  /** Texto secundário ao lado do label, ex.: "(opcional)". */
  hint?: string
  htmlFor: string
  children: ReactNode
}

/** Label (14px/600) + controle, com 8px de espaço entre eles. */
export function Field({ label, hint, htmlFor, children }: FieldProps) {
  return (
    <div className="flex min-w-0 flex-1 flex-col gap-2">
      <label htmlFor={htmlFor} className="text-sm leading-none font-semibold text-text">
        {label}
        {hint && <span className="font-normal text-text-placeholder"> {hint}</span>}
      </label>
      {children}
    </div>
  )
}
