import type { ReactNode } from 'react'
import { useNavigate } from 'react-router'
import { cx } from '../../lib/cx'
import { formatarRecebido, ROTULO_DESTINO_CURTO, rotaDaLinha, rotuloTipoCurto, scoreDaLinha } from '../../lib/filasTriagens'
import type { LinhaTriagem } from '../../lib/filasTriagens'
import { tomDoStatus } from '../../lib/resultadoTriagem'
import { PRIORIDADE } from '../../lib/rotulos'
import { Badge, Button } from '../ui'

const COLUNAS: Array<{ titulo: string; largura: string; classe?: string }> = [
  { titulo: 'Documento', largura: 'w-50', classe: 'px-5' },
  { titulo: 'Tipo', largura: 'w-40' },
  { titulo: 'Prioridade', largura: 'w-30' },
  { titulo: 'Status', largura: 'w-40' },
  { titulo: 'Destino(s)', largura: 'w-42.5' },
  { titulo: 'Score', largura: 'w-27.5' },
  { titulo: 'Recebido', largura: 'w-22.5' },
  { titulo: 'Ação', largura: 'w-25', classe: 'text-right' },
]

type TabelaTriagensProps = {
  linhas: readonly LinhaTriagem[]
  /** Mensagem quando não há linhas (lista vazia, fila vazia ou busca sem resultado). */
  vazio: ReactNode
}

export function TabelaTriagens({ linhas, vazio }: TabelaTriagensProps) {
  const navigate = useNavigate()

  if (linhas.length === 0) {
    return <div className="border-t border-border-subtle px-5 py-10 text-center text-[15px] text-text-secondary">{vazio}</div>
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-277.5 table-fixed border-collapse">
        <thead className="bg-subtle">
          <tr>
            {COLUNAS.map((c) => (
              <th
                key={c.titulo}
                scope="col"
                className={cx('py-3 text-left text-sm font-semibold text-text-secondary', c.largura, c.classe ?? 'px-3')}
              >
                {c.titulo === 'Ação' ? <span className="sr-only">Ação</span> : c.titulo}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {linhas.map((l) => {
            const prioridade = l.prioridade ? PRIORIDADE[l.prioridade] : null
            const score = scoreDaLinha(l)
            return (
              <tr key={l.documentoId} className="border-t border-border-subtle">
                <td className="px-5 py-3.5 align-middle">
                  <div className="flex flex-col gap-0.5">
                    <span className="font-mono text-caption font-medium break-all text-text">{l.documentoId}</span>
                    <span className="text-caption text-text-secondary">{l.canal ?? '—'}</span>
                  </div>
                </td>
                <td className="px-3 py-3.5 text-sm text-text">{rotuloTipoCurto(l.tipo)}</td>
                <td className="px-3 py-3.5">
                  {prioridade ? <Badge tone={prioridade.tom}>{prioridade.rotulo}</Badge> : <span className="text-text-secondary">—</span>}
                </td>
                <td className="px-3 py-3.5">
                  <Badge tone={tomDoStatus(l.status)}>{l.status}</Badge>
                </td>
                <td className="px-3 py-3.5 text-sm text-text">
                  {l.destinos.length === 0 ? (
                    '—'
                  ) : (
                    <div className="flex flex-col gap-0.5">
                      {l.destinos.map((d) => (
                        <span key={d}>{ROTULO_DESTINO_CURTO[d]}</span>
                      ))}
                    </div>
                  )}
                </td>
                <td className="px-3 py-3.5">
                  {score ? (
                    <div className="flex flex-col gap-0.5">
                      <span className="font-mono text-sm text-text">{score.valor}</span>
                      {score.abaixo && <span className="text-caption font-medium text-status-warning-fg">{score.abaixo}</span>}
                    </div>
                  ) : (
                    <span className="text-text-secondary">—</span>
                  )}
                </td>
                <td className="px-3 py-3.5 font-mono text-xs text-text-body">{formatarRecebido(l.enviadoEm)}</td>
                <td className="px-3 py-3.5 text-right">
                  <Button variant="secondary" size="S" aria-label={`Abrir ${l.documentoId}`} onClick={() => navigate(rotaDaLinha(l))}>
                    Abrir
                  </Button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
