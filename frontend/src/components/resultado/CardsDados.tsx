import type { ReactNode } from 'react'
import { cx } from '../../lib/cx'
import {
  conflitosDoMedicamento,
  formatarCrm,
  formatarEspecialidade,
  formatarIdade,
  rotuloSinalizacao,
  situacaoDoCampo,
  TOM_GRAVIDADE,
} from '../../lib/resultadoTriagem'
import { CAMPOS_OBRIGATORIOS, PRIORIDADE, rotuloTipoDocumento, URGENCIA } from '../../lib/rotulos'
import type { Medicamento, TriagemMediFlow } from '../../types/clinical'
import { Badge } from '../ui'
import { Card, Tag, ValorAusente } from './Card'

const rotuloCampo = 'text-caption text-text-secondary'

export function CardClassificacao({ triagem }: { triagem: TriagemMediFlow }) {
  const c = triagem.classificacao
  const prioridade = c ? PRIORIDADE[c.nivel_prioridade] : null
  const especialidade = formatarEspecialidade(c?.especialidade)

  return (
    <Card titulo="Classificação">
      <dl className="m-0 grid grid-cols-3 gap-4">
        <div className="flex flex-col gap-1">
          <dt className={rotuloCampo}>Tipo de documento</dt>
          <dd className="m-0 flex flex-col">
            <span className="text-base font-semibold text-text">{rotuloTipoDocumento(c?.tipo_documento ?? 'NAO_IDENTIFICADO')}</span>
            <span className="font-mono text-xs text-text-secondary">{c?.tipo_documento ?? 'NAO_IDENTIFICADO'}</span>
          </dd>
        </div>
        <div className="flex flex-col gap-1">
          <dt className={rotuloCampo}>Especialidade</dt>
          <dd className="m-0 text-base font-semibold text-text">
            {especialidade ?? <span className="text-text-secondary italic">Não identificada no documento</span>}
          </dd>
        </div>
        <div className="flex flex-col gap-1.5">
          <dt className={rotuloCampo}>Prioridade</dt>
          <dd className="m-0">
            {prioridade ? (
              <Badge tone={prioridade.tom} size="L">
                {prioridade.rotulo}
              </Badge>
            ) : (
              <ValorAusente texto="Não classificada" />
            )}
          </dd>
        </div>
      </dl>
    </Card>
  )
}

type CampoProps = { triagem: TriagemMediFlow; caminho: string; rotulo: string; valor: string | null }

function Campo({ triagem, caminho, rotulo, valor }: CampoProps) {
  const situacao = situacaoDoCampo(triagem, caminho, valor)
  return (
    <div className="flex min-w-0 flex-1 flex-col gap-1.5 self-stretch rounded-md border border-border-subtle bg-surface p-3.5">
      <div className="flex items-baseline justify-between gap-2">
        <span className={rotuloCampo}>{rotulo}</span>
        {CAMPOS_OBRIGATORIOS.has(caminho) && <span className="text-caption text-text-placeholder">obrigatório</span>}
      </div>
      {situacao.tipo === 'ausente' ? (
        <>
          <ValorAusente />
          <Tag tom={situacao.exigeRevisao ? 'warning' : 'neutral'}>
            {situacao.exigeRevisao ? 'Ausente · exige revisão' : 'Ausente · não exige revisão'}
          </Tag>
        </>
      ) : (
        <>
          <span className="text-base font-semibold break-words text-text">{valor}</span>
          {situacao.tipo === 'incerto' && <Tag tom="warning">Incerto · confirmar na revisão</Tag>}
        </>
      )}
    </div>
  )
}

export function CardDadosExtraidos({ triagem }: { triagem: TriagemMediFlow }) {
  const d = triagem.dados_extraidos
  const linhas: Array<[CampoProps, CampoProps]> = [
    [
      { triagem, caminho: 'paciente.nome', rotulo: 'Paciente', valor: d?.paciente.nome ?? null },
      { triagem, caminho: 'paciente.idade', rotulo: 'Idade', valor: formatarIdade(d?.paciente.idade) },
    ],
    [
      { triagem, caminho: 'medico.nome', rotulo: 'Médico solicitante', valor: d?.medico.nome ?? null },
      { triagem, caminho: 'medico.crm', rotulo: 'CRM', valor: formatarCrm(d?.medico.crm) },
    ],
    [
      { triagem, caminho: 'diagnostico', rotulo: 'Diagnóstico / hipótese', valor: d?.diagnostico ?? null },
      { triagem, caminho: 'cid', rotulo: 'CID-10', valor: d?.cid ?? null },
    ],
  ]

  return (
    <Card titulo="Dados extraídos" subtitulo="Somente o que está escrito no documento — nada é completado por inferência.">
      <div className="flex flex-col gap-3">
        {linhas.map(([a, b]) => (
          <div key={a.caminho} className="flex gap-3">
            <Campo {...a} />
            <Campo {...b} />
          </div>
        ))}
      </div>
    </Card>
  )
}

function comoMedicamento(item: Medicamento | string): Medicamento {
  return typeof item === 'string' ? { nome: item } : item
}

const celula = 'px-3 py-3 text-sm leading-normal text-left align-top'

export function CardMedicamentos({ triagem }: { triagem: TriagemMediFlow }) {
  const medicamentos = (triagem.dados_extraidos?.medicamentos ?? []).map(comoMedicamento)
  const conflitos = triagem.qualidade?.conflitos ?? []

  return (
    <Card titulo="Medicamentos" gap="gap-3.5">
      {medicamentos.length === 0 ? (
        <p className="m-0 text-[15px] text-text-secondary italic">Nenhum medicamento identificado no documento.</p>
      ) : (
        <div className="overflow-x-auto rounded-md border border-border-subtle">
          <table className="w-full border-collapse">
            <thead className="bg-subtle">
              <tr>
                {['Medicamento', 'Dose', 'Frequência', 'Sinalização'].map((titulo) => (
                  <th key={titulo} scope="col" className="px-3 py-2.5 text-left text-sm font-semibold text-text-secondary">
                    {titulo}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {medicamentos.map((m, indice) => {
                const sinais = conflitosDoMedicamento(conflitos, indice)
                const doseSuspeita = sinais.some((s) => s.campos.some((c) => /dose|dosagem/.test(c)))
                return (
                  <tr key={`${m.nome}-${indice}`} className="border-t border-border-subtle">
                    <td className={cx(celula, 'font-semibold text-text')}>{m.nome}</td>
                    <td className={cx(celula, 'font-semibold text-text', doseSuspeita && 'bg-status-warning-bg')}>
                      {m.dosagem ?? <span className="font-normal text-text-secondary">não consta</span>}
                    </td>
                    <td className={cx(celula, 'text-text-body')}>
                      {m.frequencia ?? <span className="text-text-secondary">não consta</span>}
                    </td>
                    <td className={celula}>
                      <div className="flex flex-wrap gap-x-1 gap-y-1">
                        {sinais.length === 0 ? (
                          <span className="text-text-secondary">—</span>
                        ) : (
                          sinais.map((s) => (
                            <Tag key={s.tipo} tom={TOM_GRAVIDADE[s.gravidade] === 'warning' ? 'chip' : TOM_GRAVIDADE[s.gravidade]}>
                              {rotuloSinalizacao(s)}
                            </Tag>
                          ))
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}

function ColunaExames({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <div className="flex min-w-0 flex-1 flex-col gap-2.5">
      <span className={rotuloCampo}>{titulo}</span>
      {children}
    </div>
  )
}

const Vazio = () => <p className="m-0 text-sm leading-normal text-text-secondary italic">Nenhum identificado no documento</p>
const Item = ({ children }: { children: ReactNode }) => (
  <li className="rounded-sm bg-app px-3 py-2 text-[15px] text-text">{children}</li>
)

export function CardExames({ triagem }: { triagem: TriagemMediFlow }) {
  const d = triagem.dados_extraidos
  const exames = d?.exames ?? []
  const laboratoriais = d?.exames_laboratoriais ?? []
  const urgencia = URGENCIA[d?.urgencia ?? 'INDETERMINADO']
  const notas = [d?.achados_criticos, ...(d?.inconsistencias_detectadas ?? [])].filter(Boolean) as string[]

  return (
    <Card titulo="Exames e urgência">
      <div className="flex gap-5">
        <ColunaExames titulo="Exames identificados">
          {exames.length === 0 ? (
            <Vazio />
          ) : (
            <ul className="m-0 flex list-none flex-col gap-1.5 p-0">
              {exames.map((e) => (
                <Item key={e}>{e}</Item>
              ))}
            </ul>
          )}
        </ColunaExames>
        <ColunaExames titulo="Exames laboratoriais">
          {laboratoriais.length === 0 ? (
            <Vazio />
          ) : (
            <ul className="m-0 flex list-none flex-col gap-1.5 p-0">
              {laboratoriais.map((e) => (
                <Item key={e.analito}>
                  {e.analito}: {e.valor_medido}
                  {e.unidade ? ` ${e.unidade}` : ''}
                  {e.alterado ? ' (alterado)' : ''}
                </Item>
              ))}
            </ul>
          )}
        </ColunaExames>
        <ColunaExames titulo="Sinais de urgência">
          <Badge tone={urgencia.tom} size="L" className="w-fit">
            {urgencia.rotulo}
          </Badge>
          {notas.length === 0 ? (
            <p className="m-0 border-l-2 border-border-input pl-2.5 text-sm leading-normal text-text-body">
              Nenhum achado crítico identificado.
            </p>
          ) : (
            notas.map((n) => (
              <p key={n} className="m-0 border-l-2 border-border-input pl-2.5 text-sm leading-normal text-text-body">
                {n}
              </p>
            ))
          )}
        </ColunaExames>
      </div>
    </Card>
  )
}
