import type { EstadoEtapa } from '../../lib/etapasProcessamento'
import { Icon } from '../ui'

type MarcadorEtapaProps = {
  estado: EstadoEtapa
}

/** Marcador de 24 px da etapa. O significado também está no texto de status ao lado, não só na cor. */
export function MarcadorEtapa({ estado }: MarcadorEtapaProps) {
  if (estado === 'concluido') {
    return (
      <span
        aria-hidden="true"
        className="flex size-6 shrink-0 items-center justify-center rounded-full bg-status-success-fg text-on-primary"
      >
        <Icon name="check" size={14} />
      </span>
    )
  }

  if (estado === 'falhou') {
    return (
      <span
        aria-hidden="true"
        className="flex size-6 shrink-0 items-center justify-center rounded-full bg-status-danger-fg text-on-primary"
      >
        <Icon name="alert" size={14} />
      </span>
    )
  }

  if (estado === 'andamento') {
    // Anel azul com ponto central (Figma 53:315). O ponto pulsa, exceto com "reduzir movimento".
    return (
      <span
        aria-hidden="true"
        className="flex size-6 shrink-0 items-center justify-center rounded-full border-2 border-primary"
      >
        <span className="size-2 rounded-full bg-primary motion-safe:animate-pulse" />
      </span>
    )
  }

  return <span aria-hidden="true" className="size-6 shrink-0 rounded-full border-2 border-border-input bg-surface" />
}
