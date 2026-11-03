import { Link, useNavigate, useParams } from 'react-router'
import { BarraProgresso, ListaEtapas } from '../components/processamento'
import { Badge, Button, Icon } from '../components/ui'
import { useAcompanharTriagem } from '../hooks/useAcompanharTriagem'
import { badgeDoStatus, derivarEtapas } from '../lib/etapasProcessamento'
import type { StatusTriagem } from '../types/clinical'

const MENSAGEM_ERRO_PADRAO: Partial<Record<StatusTriagem, string>> = {
  ERRO_PROCESSAMENTO: 'O servidor não conseguiu processar este documento. Envie uma nova triagem.',
  ERRO_PERSISTENCIA:
    'A decisão foi calculada, mas o resultado não pôde ser salvo. O documento pode ser reprocessado depois.',
}

/** Tela 02a/02b do Figma: acompanha a triagem enviada até um estado final. */
export function ProcessamentoPage() {
  const { documentoId } = useParams()
  const navigate = useNavigate()
  const acompanhamento = useAcompanharTriagem(documentoId)
  const { status, erro, resultado, motivoErro } = acompanhamento

  const progresso = derivarEtapas({
    status,
    etapaVisual: acompanhamento.etapaVisual,
    caminhoResultado: resultado?.armazenamento_oci?.caminho_objeto,
  })
  const badge = badgeDoStatus(status)

  const falhou = status === 'ERRO_PROCESSAMENTO' || status === 'ERRO_PERSISTENCIA'
  // Com erro de persistência a decisão existe e pode ser vista; com erro de processamento não há resultado.
  const podeVerResultado = acompanhamento.terminal && status !== 'ERRO_PROCESSAMENTO'

  return (
    <div className="flex flex-col gap-6">
      <Link
        to="/nova-triagem"
        className="inline-flex w-fit items-center gap-1.5 py-3 text-sm leading-normal font-medium text-link hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
      >
        <Icon name="back" size={16} />
        Nova triagem
      </Link>

      <div className="flex items-start gap-6">
        <section
          aria-labelledby="titulo-status"
          className="flex min-w-0 flex-1 flex-col gap-6 rounded-lg border border-border bg-surface p-7"
        >
          <h1 id="titulo-status" className="sr-only">
            Status da triagem
          </h1>

          <div className="flex items-start justify-between gap-4">
            <div className="flex min-w-0 flex-col gap-1.5">
              <span className="text-caption font-medium text-text-secondary">Documento</span>
              <span className="font-mono text-2xl leading-tight font-medium break-all text-text">{documentoId}</span>
            </div>
            <Badge tone={badge.tom} size="L" className="shrink-0">
              {badge.rotulo}
            </Badge>
          </div>

          <BarraProgresso porcentagem={progresso.porcentagem} rotulo={progresso.rotuloBarra} />

          {erro && (
            <div role="alert" className="flex items-start gap-3 rounded-md bg-status-danger-bg p-4 text-status-danger-fg">
              <Icon name="alert" size={20} className="mt-px shrink-0" />
              <div className="flex flex-col gap-2">
                <p className="m-0 text-sm font-semibold">Não foi possível acompanhar a triagem</p>
                <p className="m-0 text-caption">{erro.mensagem}</p>
                {erro.codigo !== 'DOCUMENTO_NAO_ENCONTRADO' && (
                  <div>
                    <Button variant="secondary" size="S" onClick={acompanhamento.tentarNovamente}>
                      Tentar novamente
                    </Button>
                  </div>
                )}
              </div>
            </div>
          )}

          {falhou && status && (
            <div role="alert" className="flex items-start gap-3 rounded-md bg-status-danger-bg p-4 text-status-danger-fg">
              <Icon name="alert" size={20} className="mt-px shrink-0" />
              <div className="flex flex-col gap-1">
                <p className="m-0 text-sm font-semibold">A triagem não foi concluída</p>
                <p className="m-0 text-caption">{motivoErro ?? MENSAGEM_ERRO_PADRAO[status]}</p>
              </div>
            </div>
          )}

          <ListaEtapas etapas={progresso.etapas} />

          <div className="flex items-center gap-3">
            {podeVerResultado && (
              <Button withIcon onClick={() => navigate(`/resultado/${encodeURIComponent(documentoId ?? '')}`)}>
                Ver resultado
              </Button>
            )}
            <Button variant="secondary" onClick={() => navigate('/nova-triagem')}>
              Simular de novo
            </Button>
          </div>
        </section>
      </div>
    </div>
  )
}
