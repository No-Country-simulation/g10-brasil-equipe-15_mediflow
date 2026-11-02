import { CaseCard } from './CaseCard'
import { CASOS_TESTE } from './casosTeste'
import type { CasoTeste } from './casosTeste'

type CasosTestePanelProps = {
  selecionadoId: CasoTeste['id'] | null
  carregando: boolean
  erro: string | null
  onSelecionar: (caso: CasoTeste) => void
}

export function CasosTestePanel({ selecionadoId, carregando, erro, onSelecionar }: CasosTestePanelProps) {
  return (
    <aside
      aria-label="Casos de teste"
      aria-busy={carregando}
      className="flex w-91.5 shrink-0 flex-col gap-3 rounded-lg border border-border bg-surface p-5"
    >
      <div className="flex flex-col gap-1">
        <h2 className="m-0 text-base leading-tight font-semibold text-text">Casos de teste</h2>
        <p className="m-0 text-caption text-text-secondary">
          Os três cenários da demonstração, com documentos fictícios.
        </p>
      </div>

      {CASOS_TESTE.map((caso) => (
        <CaseCard key={caso.id} caso={caso} selecionado={caso.id === selecionadoId} onSelecionar={onSelecionar} />
      ))}

      {erro && (
        <p role="alert" className="m-0 text-caption text-status-danger-fg">
          {erro}
        </p>
      )}
    </aside>
  )
}
