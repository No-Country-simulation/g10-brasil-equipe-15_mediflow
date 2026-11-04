import type { ReactNode } from 'react'
import { useId, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import {
  AlertaErro,
  BannerResultado,
  CardArmazenamento,
  CardClassificacao,
  CardConfianca,
  CardConflitos,
  CardDadosExtraidos,
  CardExames,
  CardMedicamentos,
  CardRoteamento,
  Historico,
  PainelJson,
} from '../components/resultado'
import { Badge, Button, Icon } from '../components/ui'
import { useResultadoTriagem } from '../hooks/useResultadoTriagem'
import { formatarDataHora } from '../lib/dadosEnvio'
import { alertaDeErro, bannersDe, tomDoStatus } from '../lib/resultadoTriagem'

const linkVoltar =
  'inline-flex w-fit items-center gap-1.5 py-3 text-sm leading-normal font-medium text-link hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary'

function Aviso({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-md bg-status-danger-bg p-4 text-status-danger-fg">
      <Icon name="alert" size={20} className="mt-px shrink-0" />
      <div className="flex flex-col gap-2">
        <p className="m-0 text-sm font-semibold">{titulo}</p>
        {children}
      </div>
    </div>
  )
}

/** Telas 03a–03e do Figma: resultado completo de uma triagem concluída. */
export function ResultadoPage() {
  const { documentoId = '' } = useParams()
  const navigate = useNavigate()
  const idPainel = useId()
  const [mostrarJson, setMostrarJson] = useState(false)
  const { estado, recarregar, reprocessar, reprocessamento } = useResultadoTriagem(documentoId)

  const voltar = (
    <Link to="/triagens" className={linkVoltar}>
      <Icon name="back" size={16} />
      Triagens e filas
    </Link>
  )

  if (estado.fase === 'carregando') {
    return (
      <div className="flex flex-col gap-5">
        {voltar}
        <p role="status" className="m-0 text-text-secondary">
          Carregando o resultado…
        </p>
      </div>
    )
  }

  if (estado.fase === 'em_andamento') {
    return (
      <div className="flex flex-col gap-5">
        {voltar}
        <div role="status" className="flex flex-col gap-2 rounded-lg border border-border-info bg-selected p-5">
          <p className="m-0 text-[15px] font-semibold text-text">A triagem ainda está em processamento</p>
          <p className="m-0 text-sm text-info-panel-text">
            Status atual: <span className="font-mono">{estado.status}</span>. O resultado aparece aqui quando terminar.{' '}
            <Link to={`/nova-triagem/processamento/${encodeURIComponent(documentoId)}`} className="text-link hover:underline">
              Acompanhar o processamento
            </Link>
          </p>
        </div>
      </div>
    )
  }

  if (estado.fase === 'erro') {
    return (
      <div className="flex flex-col gap-5">
        {voltar}
        <Aviso titulo="Não foi possível carregar o resultado">
          <p className="m-0 text-caption">{estado.mensagem}</p>
          {estado.codigo !== 'DOCUMENTO_NAO_ENCONTRADO' && (
            <div>
              <Button variant="secondary" size="S" onClick={recarregar}>
                Tentar novamente
              </Button>
            </div>
          )}
        </Aviso>
      </div>
    )
  }

  const { triagem, bruto, historico } = estado
  const alerta = alertaDeErro(triagem)
  const recebidoEm = historico.find((e) => e.tipo_evento === 'RECEBIDO')?.criado_em ?? null
  const metadado = [
    recebidoEm ? `Recebido ${formatarDataHora(recebidoEm)}` : null,
    triagem.canal_origem,
    triagem.versao_esquema && triagem.versao_esquema !== 'desconhecida' ? `esquema v${triagem.versao_esquema}` : null,
  ]
    .filter(Boolean)
    .join(' · ')

  return (
    <div className="flex flex-col gap-5">
      {voltar}

      <header className="flex items-end justify-between gap-4">
        <div className="flex min-w-0 flex-col gap-2">
          <h1 className="m-0 text-caption font-medium text-text-secondary">Resultado da triagem</h1>
          <div className="flex flex-wrap items-center gap-3">
            <span className="font-mono text-[26px] leading-tight font-medium break-all text-text">{triagem.documento_id}</span>
            <Badge tone={tomDoStatus(triagem.status)} size="L">
              {triagem.status}
            </Badge>
          </div>
          {metadado && <p className="m-0 text-sm leading-normal text-text-secondary">{metadado}</p>}
        </div>
        <button
          type="button"
          aria-expanded={mostrarJson}
          aria-controls={idPainel}
          onClick={() => setMostrarJson((v) => !v)}
          className="inline-flex h-11 shrink-0 cursor-pointer items-center gap-2 rounded-md border border-border-input bg-surface px-4 text-sm font-medium text-text transition-colors hover:bg-subtle focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
        >
          <Icon name="code" size={16} />
          {mostrarJson ? 'Ocultar JSON da resposta' : 'Ver JSON da resposta'}
        </button>
      </header>

      {mostrarJson && <PainelJson id={idPainel} dados={bruto} />}

      {alerta ? (
        <AlertaErro
          alerta={alerta}
          reprocessando={reprocessamento.fase === 'enviando'}
          erroReprocesso={reprocessamento.fase === 'erro' ? reprocessamento.mensagem : null}
          onReprocessar={reprocessar}
          onReenviar={() => navigate('/nova-triagem')}
        />
      ) : (
        <>
          {bannersDe(triagem).map((banner) => (
            <BannerResultado key={banner.tipo} banner={banner} />
          ))}
          <div className="flex items-start gap-5">
            <div className="flex min-w-0 flex-1 flex-col gap-5">
              <CardClassificacao triagem={triagem} />
              <CardDadosExtraidos triagem={triagem} />
              <CardMedicamentos triagem={triagem} />
              <CardExames triagem={triagem} />
            </div>
            <div className="flex w-93 shrink-0 flex-col gap-5">
              <CardConfianca triagem={triagem} />
              <CardConflitos triagem={triagem} />
              <CardRoteamento triagem={triagem} />
              <CardArmazenamento triagem={triagem} />
            </div>
          </div>
        </>
      )}

      <Historico eventos={historico} />
    </div>
  )
}
