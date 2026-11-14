import type { ReactNode } from 'react'
import { cx } from '../../lib/cx'
import { confiancaDe, formatarScore, situacaoDoAlerta, textoFalhaAlerta, TOM_DESTINO } from '../../lib/resultadoTriagem'
import { ROTULO_DESTINO, ROTULO_GRAVIDADE, rotuloStatusBackup } from '../../lib/rotulos'
import type { Destino, TriagemMediFlow } from '../../types/clinical'
import { Icon } from '../ui'
import { Card, Tag } from './Card'

type BarraScoreProps = { rotulo: string; valor: number; destaque?: boolean; abaixo?: boolean; limiar?: number }

function BarraScore({ rotulo, valor, destaque = false, abaixo = false, limiar }: BarraScoreProps) {
  const pct = Math.min(100, Math.max(0, valor * 100))
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between gap-2 text-sm leading-normal">
        <span className={cx('text-text-body', destaque && 'font-semibold')}>{rotulo}</span>
        <span className="font-mono text-text">{formatarScore(valor)}</span>
      </div>
      <div
        role="meter"
        aria-label={`Score de ${rotulo.toLowerCase()}`}
        aria-valuemin={0}
        aria-valuemax={1}
        aria-valuenow={valor}
        className="relative h-2.5 rounded-full bg-progress-track"
      >
        <div
          className={cx('h-full rounded-full', !destaque ? 'bg-progress-muted' : abaixo ? 'bg-status-warning-fg' : 'bg-primary')}
          style={{ width: `${pct}%` }}
        />
        {limiar !== undefined && (
          <span
            aria-hidden="true"
            className="absolute -top-1 h-4.5 w-0.5 bg-text"
            style={{ left: `calc(${limiar * 100}% - 1px)` }}
          />
        )}
      </div>
    </div>
  )
}

export function CardConfianca({ triagem }: { triagem: TriagemMediFlow }) {
  const c = confiancaDe(triagem)
  if (!c) {
    return (
      <Card titulo="Confiança">
        <p className="m-0 text-[15px] text-text-secondary">Scores não informados.</p>
      </Card>
    )
  }
  const limiar = formatarScore(c.limiar)
  return (
    <Card titulo="Confiança" gap="gap-4.5">
      <BarraScore rotulo="Classificação" valor={c.classificacao} />
      <BarraScore rotulo="Extração" valor={c.extracao} />
      <div className="flex flex-col gap-1.5">
        <BarraScore rotulo="Combinado" valor={c.combinado} destaque abaixo={c.abaixoDoLimiar} limiar={c.limiar} />
        <p className={cx('m-0 text-caption font-medium', c.abaixoDoLimiar ? 'text-status-warning-fg' : 'text-status-info-fg')}>
          {c.abaixoDoLimiar
            ? `Abaixo do limiar ${limiar} — exige revisão humana`
            : `Score atingiu o limiar ${limiar}`}
        </p>
      </div>
      {c.formula && (
        <p className="m-0 rounded-sm bg-subtle p-3 font-mono text-xs leading-normal text-text-body">{c.formula}</p>
      )}
    </Card>
  )
}

export function CardConflitos({ triagem }: { triagem: TriagemMediFlow }) {
  const conflitos = triagem.qualidade?.conflitos ?? []
  return (
    <Card titulo="Conflitos" gap="gap-3.5">
      {conflitos.length === 0 ? (
        <p className="m-0 text-[15px] text-text-secondary">Nenhum conflito detectado.</p>
      ) : (
        conflitos.map((c, i) => (
          <div
            key={`${c.tipo}-${i}`}
            className="flex flex-col gap-2 rounded-md border border-status-warning-border bg-status-warning-soft p-3.5"
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-caption font-medium text-text">{c.tipo}</span>
              <Tag tom={c.gravidade === 'ALTA' ? 'danger' : c.gravidade === 'MEDIA' ? 'chip' : 'neutral'}>
                {ROTULO_GRAVIDADE[c.gravidade]}
              </Tag>
            </div>
            <p className="m-0 text-sm leading-normal text-text-body">{c.descricao}</p>
            {c.campos.length > 0 && (
              <p className="m-0 text-caption text-text-secondary">
                {c.campos.length === 1 ? 'Campo: ' : 'Campos: '}
                <span className="font-mono text-xs text-text-body">{c.campos.join(', ')}</span>
              </p>
            )}
          </div>
        ))
      )}
    </Card>
  )
}

const ESTILO_DESTINO = {
  success: 'bg-status-success-bg text-status-success-strong',
  danger: 'bg-status-danger-bg text-status-danger-dark',
  warning: 'bg-status-warning-bg text-status-warning-banner',
  info: 'bg-status-info-bg text-status-info-fg',
} as const

function Linha({ rotulo, children }: { rotulo: string; children: ReactNode }) {
  return (
    <div className="flex gap-4 text-sm leading-normal">
      <dt className="w-24 shrink-0 text-text-secondary">{rotulo}</dt>
      <dd className="m-0 min-w-0 text-text">{children}</dd>
    </div>
  )
}

export function CardRoteamento({ triagem }: { triagem: TriagemMediFlow }) {
  const r = triagem.decisao_roteamento
  const destinos: Destino[] = r?.destinos.length ? r.destinos : r?.destino_principal ? [r.destino_principal] : []
  const alerta = situacaoDoAlerta(triagem)

  return (
    <Card titulo="Decisão de roteamento">
      <div className="flex flex-col gap-2">
        <span className="text-caption text-text-secondary">Destino(s) lógico(s) · simulados</span>
        {destinos.length === 0 ? (
          <p className="m-0 text-[15px] text-text-secondary">Nenhum destino definido.</p>
        ) : (
          <ul className="m-0 flex list-none flex-col gap-2 p-0">
            {destinos.map((d) => (
              <li key={d} className={cx('flex flex-col gap-0.5 rounded-md px-3.5 py-3', ESTILO_DESTINO[TOM_DESTINO[d]])}>
                <span className="text-[15px] font-semibold">{ROTULO_DESTINO[d]}</span>
                <span className="font-mono text-xs">{d}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
      <dl className="m-0 flex flex-col gap-2.5">
        <Linha rotulo="Revisão humana">
          <span className="font-semibold">{r?.requer_auditoria_humana ? 'Sim' : 'Não'}</span>
        </Linha>
        <Linha rotulo="Alerta">
          {alerta.tipo === 'registrado' ? (
            `Evento simulado registrado (${alerta.canal})`
          ) : alerta.tipo === 'falhou' ? (
            <span className="font-semibold text-status-danger-fg">{textoFalhaAlerta(alerta.status)}</span>
          ) : (
            'Nenhum alerta gerado'
          )}
        </Linha>
        <Linha rotulo="Justificativa">{r?.justificativa_roteamento || '—'}</Linha>
      </dl>
    </Card>
  )
}

export function CardArmazenamento({ triagem }: { triagem: TriagemMediFlow }) {
  const oci = triagem.armazenamento_oci
  const salvo = oci?.status_backup?.toLowerCase() === 'sucesso'
  return (
    <Card titulo="Armazenamento OCI" gap="gap-3">
      {!oci ? (
        <p className="m-0 text-[15px] text-text-secondary">A API não informou o armazenamento deste resultado.</p>
      ) : (
        <dl className="m-0 flex flex-col gap-2">
          <div className="flex gap-4 text-sm leading-normal">
            <dt className="w-16 shrink-0 text-text-secondary">Status</dt>
            <dd className={cx('m-0 inline-flex items-center gap-1.5 font-semibold', salvo ? 'text-status-success-fg' : 'text-text')}>
              {salvo && <Icon name="check" size={16} />}
              {rotuloStatusBackup(oci.status_backup)}
              {oci.modo_simulacao && <span className="font-normal text-text-secondary">(simulado)</span>}
            </dd>
          </div>
          {[
            ['Bucket', oci.bucket],
            ['Objeto', oci.caminho_objeto],
          ].map(([rotulo, valor]) => (
            <div key={rotulo} className="flex gap-4 text-sm leading-normal">
              <dt className="w-16 shrink-0 text-text-secondary">{rotulo}</dt>
              <dd className="m-0 min-w-0 font-mono text-xs leading-6 break-all text-text">{valor || '—'}</dd>
            </div>
          ))}
        </dl>
      )}
    </Card>
  )
}
