import { useEffect, useRef, useState } from 'react'
import { formatarDataHora, SEM_DADO } from '../../lib/dadosEnvio'
import type { DadosEnvio } from '../../lib/dadosEnvio'
import { Icon } from '../ui'

type CardEnvioProps = {
  documentoId: string
  /** Dados vindos do formulário; `null` em acesso direto pela URL. */
  envio: DadosEnvio | null
  /** Hora do evento RECEBIDO no histórico; tem prioridade sobre a hora do navegador. */
  enviadoEm: string | null
}

const TEMPO_AVISO_COPIADO_MS = 2000

type Copia = 'ocioso' | 'copiado' | 'falhou'

export function CardEnvio({ documentoId, envio, enviadoEm }: CardEnvioProps) {
  const [copia, setCopia] = useState<Copia>('ocioso')
  const temporizador = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  useEffect(() => () => clearTimeout(temporizador.current), [])

  async function copiar() {
    let resultado: Copia = 'copiado'
    try {
      await navigator.clipboard.writeText(documentoId)
    } catch {
      resultado = 'falhou'
    }
    setCopia(resultado)
    clearTimeout(temporizador.current)
    temporizador.current = setTimeout(() => setCopia('ocioso'), TEMPO_AVISO_COPIADO_MS)
  }

  const linhas: Array<{ rotulo: string; valor: string; mono?: boolean }> = [
    { rotulo: 'Formato', valor: envio?.formato ?? SEM_DADO },
    { rotulo: 'Canal', valor: envio?.canal ?? SEM_DADO },
    { rotulo: 'Enviado', valor: formatarDataHora(enviadoEm ?? envio?.enviadoEm) },
    // O 202 só é conhecido quando o envio foi feito nesta sessão.
    { rotulo: 'Resposta', valor: envio ? '202 Accepted' : SEM_DADO, mono: Boolean(envio) },
  ]

  return (
    <section aria-labelledby="titulo-envio" className="flex flex-col gap-3.5 rounded-lg border border-border bg-surface p-5">
      <h2 id="titulo-envio" className="m-0 text-base leading-tight font-semibold text-text">
        Envio
      </h2>

      <dl className="m-0 flex flex-col gap-2">
        {linhas.map(({ rotulo, valor, mono }) => (
          <div key={rotulo} className="flex gap-4 text-sm leading-normal">
            <dt className="w-18 shrink-0 text-text-secondary">{rotulo}</dt>
            <dd className={mono ? 'm-0 font-mono text-xs leading-6 text-text' : 'm-0 text-text'}>{valor}</dd>
          </div>
        ))}
      </dl>

      <button
        type="button"
        onClick={copiar}
        className="inline-flex h-11 w-full cursor-pointer items-center justify-center gap-2 rounded-md border border-border-input bg-surface px-3.5 text-caption font-medium text-text transition-colors hover:bg-subtle focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
      >
        <Icon name={copia === 'copiado' ? 'check' : 'copy'} size={16} />
        <span aria-live="polite">
          {copia === 'copiado' ? 'ID copiado' : copia === 'falhou' ? 'Não foi possível copiar' : 'Copiar ID do documento'}
        </span>
      </button>
    </section>
  )
}
