import type { Etapa } from '../../lib/etapasProcessamento'
import { EtapaItem } from './EtapaItem'

type ListaEtapasProps = {
  etapas: readonly Etapa[]
}

export function ListaEtapas({ etapas }: ListaEtapasProps) {
  return (
    <ol aria-label="Etapas da triagem" className="m-0 flex list-none flex-col p-0">
      {etapas.map((etapa) => (
        <EtapaItem key={etapa.numero} etapa={etapa} />
      ))}
    </ol>
  )
}
