import { CRM_LOGADO_TEXTO, iniciais, MEDICO_LOGADO } from '../../lib/medicoLogado'
import { Icon } from '../ui'

/** Faixa azul do Figma 04c: médico identificado e aviso de privacidade. */
export function FaixaMedico() {
  return (
    <div className="flex items-center gap-3.5 rounded-lg border border-border-info bg-selected px-4.5 py-3.5">
      <div
        aria-hidden="true"
        className="flex size-10 shrink-0 items-center justify-center rounded-full bg-primary text-[13px] font-medium text-on-primary"
      >
        {iniciais(MEDICO_LOGADO.nome)}
      </div>
      <div className="flex min-w-0 flex-col gap-0.5">
        <span className="text-[15px] font-semibold text-text">{MEDICO_LOGADO.nome}</span>
        <span className="text-caption text-text-secondary">{CRM_LOGADO_TEXTO} · dados de demonstração</span>
      </div>
      <div className="flex-1" />
      <div className="flex items-center gap-2 text-sm text-info-panel-text">
        <Icon name="lock" size={18} className="shrink-0" />
        Filtro por CRM aplicado só neste navegador, sobre os dados da demo. A API não restringe o acesso.
      </div>
    </div>
  )
}
