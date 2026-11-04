import type { ReactNode } from 'react'
import { cx } from '../../lib/cx'

type CardProps = {
  titulo: string
  subtitulo?: string
  /** Espaçamento interno entre blocos (Figma: 12 a 18 px, 16 na maioria). */
  gap?: 'gap-3' | 'gap-3.5' | 'gap-4' | 'gap-4.5'
  className?: string
  children: ReactNode
}

/** Card padrão do Resultado: superfície branca, borda, raio 12 e padding 22. */
export function Card({ titulo, subtitulo, gap = 'gap-4', className, children }: CardProps) {
  return (
    <section className={cx('flex flex-col rounded-lg border border-border bg-surface p-5.5', gap, className)}>
      <div className="flex flex-col gap-1">
        <h2 className="m-0 text-base leading-tight font-semibold text-text">{titulo}</h2>
        {subtitulo && <p className="m-0 text-caption text-text-secondary">{subtitulo}</p>}
      </div>
      {children}
    </section>
  )
}

export type TomTag = 'neutral' | 'warning' | 'danger' | 'chip' | 'regra'

const TONS_TAG: Record<TomTag, string> = {
  neutral: 'bg-status-neutral-bg text-status-neutral-fg',
  warning: 'bg-status-warning-bg text-status-warning-fg',
  danger: 'bg-status-danger-bg text-status-danger-fg',
  chip: 'bg-status-warning-chip text-status-warning-chip-fg',
  regra: 'bg-muted font-mono font-normal text-status-neutral-fg',
}

/** Chip pequeno (raio 6) usado para ausências, incertezas, gravidade e sinalizações. */
export function Tag({ tom, children }: { tom: TomTag; children: ReactNode }) {
  return (
    <span className={cx('inline-flex w-fit items-center rounded-[6px] px-2 py-0.5 text-xs leading-normal font-semibold', TONS_TAG[tom])}>
      {children}
    </span>
  )
}

/** Valor que não veio no documento: itálico, sem inventar conteúdo. */
export function ValorAusente({ texto = 'Não identificado no documento' }: { texto?: string }) {
  return <span className="text-[15px] leading-normal text-text-secondary italic">{texto}</span>
}
