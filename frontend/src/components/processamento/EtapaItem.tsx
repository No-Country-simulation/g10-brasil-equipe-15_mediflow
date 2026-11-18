import { cx } from '../../lib/cx'
import { ROTULO_ESTADO_ETAPA } from '../../lib/etapasProcessamento'
import type { Etapa, EstadoEtapa } from '../../lib/etapasProcessamento'
import { MarcadorEtapa } from './MarcadorEtapa'

const COR_DO_STATUS: Record<EstadoEtapa, string> = {
  concluido: 'text-status-success-fg',
  andamento: 'text-status-info-fg',
  aguardando: 'text-text-placeholder',
  falhou: 'text-status-danger-fg',
}

type EtapaItemProps = {
  etapa: Etapa
}

export function EtapaItem({ etapa }: EtapaItemProps) {
  const aguardando = etapa.estado === 'aguardando'

  return (
    <li
      aria-current={etapa.estado === 'andamento' ? 'step' : undefined}
      className="flex items-start gap-3.5 border-t border-border-subtle py-3"
    >
      <MarcadorEtapa estado={etapa.estado} />
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span
          className={cx(
            'text-[15px] leading-6',
            aguardando ? 'font-normal text-text-secondary' : 'font-semibold text-text',
          )}
        >
          {etapa.titulo}
        </span>
        <span
          className={cx(
            'text-caption text-text-secondary',
            etapa.mono && 'font-mono text-xs leading-[1.45] break-all',
          )}
        >
          {etapa.subtexto}
        </span>
      </div>
      <span className={cx('shrink-0 text-xs leading-6 font-semibold', COR_DO_STATUS[etapa.estado])}>
        {ROTULO_ESTADO_ETAPA[etapa.estado]}
      </span>
    </li>
  )
}
