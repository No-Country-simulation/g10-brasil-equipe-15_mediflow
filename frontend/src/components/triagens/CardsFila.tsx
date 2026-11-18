import { cx } from '../../lib/cx'
import type { Fila, IdFila } from '../../lib/filasTriagens'

type CardsFilaProps = {
  filas: readonly Fila[]
  contagens: Record<IdFila, number>
  ativa: IdFila
  onSelecionar: (fila: IdFila) => void
}

/** Cards de contagem clicáveis (seleção única), como no Figma 04a–04c. */
export function CardsFila({ filas, contagens, ativa, onSelecionar }: CardsFilaProps) {
  return (
    <div role="group" aria-label="Filtrar por fila" className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:flex">
      {filas.map((fila) => {
        const selecionada = fila.id === ativa
        return (
          <button
            key={fila.id}
            type="button"
            aria-pressed={selecionada}
            aria-label={`${fila.rotulo}: ${contagens[fila.id]}`}
            onClick={() => onSelecionar(fila.id)}
            className={cx(
              'flex min-w-px flex-1 cursor-pointer flex-col gap-2 rounded-lg bg-surface text-left transition-colors',
              'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary',
              // Borda de 2 px no ativo sem mudar o tamanho do card: o padding compensa 1 px.
              selecionada ? 'border-2 border-primary p-[15px] shadow-xs' : 'border border-border p-4 hover:bg-subtle',
            )}
          >
            <span className={cx('text-[28px] leading-none font-semibold', fila.cor)}>{contagens[fila.id]}</span>
            <span className="text-sm leading-tight font-medium text-text-body">{fila.rotulo}</span>
          </button>
        )
      })}
    </div>
  )
}
