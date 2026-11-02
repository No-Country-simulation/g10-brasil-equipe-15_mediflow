import type { EstadoEnvio } from '../../hooks/useSubmeterTriagem'
import { cx } from '../../lib/cx'
import { Icon } from '../ui'

type ResultadoEnvioProps = {
  estado: EstadoEnvio
}

/** Feedback do envio: sucesso (202) ou erro. Não renderiza nada nos demais estados. */
export function ResultadoEnvio({ estado }: ResultadoEnvioProps) {
  if (estado.fase === 'sucesso') {
    return (
      <div
        role="status"
        className={cx('flex items-start gap-3 rounded-md p-4', 'bg-status-success-bg text-status-success-fg')}
      >
        <Icon name="check" size={20} className="mt-px shrink-0" />
        <div className="flex flex-col gap-1">
          <p className="m-0 text-sm font-semibold">Documento recebido para triagem</p>
          <p className="m-0 text-caption">
            ID: <span className="font-mono">{estado.resposta.documento_id}</span> · {estado.resposta.status}
          </p>
        </div>
      </div>
    )
  }

  if (estado.fase === 'erro') {
    return (
      <div
        role="alert"
        className={cx('flex items-start gap-3 rounded-md p-4', 'bg-status-danger-bg text-status-danger-fg')}
      >
        <Icon name="alert" size={20} className="mt-px shrink-0" />
        <div className="flex flex-col gap-1">
          <p className="m-0 text-sm font-semibold">Não foi possível enviar o documento</p>
          <p className="m-0 text-caption">{estado.mensagem}</p>
        </div>
      </div>
    )
  }

  return null
}
