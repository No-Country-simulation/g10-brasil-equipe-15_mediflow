import type { AlertaErro as Alerta } from '../../lib/resultadoTriagem'
import { Button, Icon } from '../ui'

type AlertaErroProps = {
  alerta: Alerta
  reprocessando: boolean
  erroReprocesso: string | null
  onReprocessar: () => void
  onReenviar: () => void
}

/** Alerta da 03e (erro de persistência), reaproveitado para o erro de processamento. */
export function AlertaErro({ alerta, reprocessando, erroReprocesso, onReprocessar, onReenviar }: AlertaErroProps) {
  return (
    <div role="alert" className="flex items-start gap-4 rounded-lg border-2 border-text-secondary bg-surface p-6">
      <Icon name="alert" size={28} className="shrink-0 text-text" />
      <div className="flex min-w-0 flex-col gap-3">
        <p className="m-0 text-lg leading-snug font-semibold text-text">{alerta.titulo}</p>
        <p className="m-0 text-[15px] leading-normal text-text-body">{alerta.corpo}</p>
        <p className="m-0 text-caption break-words text-text-secondary">{alerta.codigo}</p>
        {erroReprocesso && <p className="m-0 text-caption text-status-danger-fg">{erroReprocesso}</p>}
        <div className="flex flex-wrap gap-2.5">
          {alerta.podeReprocessar && (
            <Button onClick={onReprocessar} disabled={reprocessando}>
              {reprocessando ? 'Salvando…' : 'Tentar salvar de novo'}
            </Button>
          )}
          <Button variant="secondary" onClick={onReenviar}>
            Reenviar documento
          </Button>
        </div>
      </div>
    </div>
  )
}
