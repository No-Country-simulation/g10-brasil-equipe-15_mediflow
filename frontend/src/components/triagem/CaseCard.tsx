import { cx } from '../../lib/cx'
import type { CasoTeste } from './casosTeste'

type CaseCardProps = {
  caso: CasoTeste
  selecionado: boolean
  onSelecionar: (caso: CasoTeste) => void
}

export function CaseCard({ caso, selecionado, onSelecionar }: CaseCardProps) {
  return (
    <button
      type="button"
      aria-pressed={selecionado}
      onClick={() => onSelecionar(caso)}
      className={cx(
        'flex w-full cursor-pointer flex-col gap-1 rounded-md border px-3.5 py-3 text-left transition-colors',
        'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary',
        // Borda de 2px no selecionado sem deslocar o layout: 1px de borda + 1px de anel interno.
        selecionado
          ? 'border-primary bg-selected ring-1 ring-primary ring-inset'
          : 'border-border bg-surface hover:bg-subtle',
      )}
    >
      <span className="flex w-full items-baseline justify-between gap-2">
        <span className="text-[15px] leading-tight font-semibold text-text">{caso.titulo}</span>
        <span className="font-mono text-xs text-text-secondary">{caso.tag}</span>
      </span>
      <span className="text-caption leading-[1.4] text-text-secondary">{caso.descricao}</span>
      <span className="text-caption font-medium text-accent">Esperado: {caso.esperado}</span>
    </button>
  )
}
