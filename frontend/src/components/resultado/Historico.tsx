import type { EventoHistorico } from '../../types/api'
import { Card } from './Card'

function dataHora(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const dia = d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' })
  const hora = d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
  return `${dia} ${hora}`
}

/** Linha do tempo de auditoria, como a API devolve (sem inventar eventos). */
export function Historico({ eventos }: { eventos: readonly EventoHistorico[] }) {
  return (
    <Card titulo="Histórico" gap="gap-3.5">
      {eventos.length === 0 ? (
        <p className="m-0 text-[15px] text-text-secondary">Nenhum evento registrado.</p>
      ) : (
        <ol aria-label="Eventos da triagem" className="m-0 flex list-none flex-col p-0">
          {eventos.map((e) => (
            <li key={e.evento_id} className="flex gap-4 border-t border-border-subtle py-3">
              <span className="w-42.5 shrink-0 font-mono text-xs leading-6 text-text-secondary">{dataHora(e.criado_em)}</span>
              <span className="w-52.5 shrink-0 font-mono text-caption leading-6 font-medium text-text">{e.tipo_evento}</span>
              <span className="w-52.5 shrink-0 font-mono text-xs leading-6 text-text-body">
                {e.status_anterior || e.status_novo ? `${e.status_anterior ?? '—'} → ${e.status_novo}` : ''}
              </span>
              <span className="min-w-0 flex-1 text-sm leading-normal break-words text-text-body">{e.motivo ?? ''}</span>
            </li>
          ))}
        </ol>
      )}
    </Card>
  )
}
