import { useNavigate } from 'react-router'
import { useSessao } from '../../hooks/useSessao'
import { Button, Icon } from '../ui'

type AcessoRestritoProps = {
  documentoId: string
  /** "CRM 88214 / RS" */
  crmDocumento: string
  /** "CRM 145892 / SP" */
  crmSessao: string
}

/** Tela 00d: documento de outro médico solicitante. */
export function AcessoRestrito({ documentoId, crmDocumento, crmSessao }: AcessoRestritoProps) {
  const navigate = useNavigate()
  const { sair } = useSessao()

  const linhas: Array<[string, string]> = [
    ['Documento', documentoId],
    ['Solicitante do documento', crmDocumento],
    ['Você está logada como', crmSessao],
  ]

  return (
    <div className="flex flex-1 items-center justify-center">
      <section aria-labelledby="titulo-restrito" className="flex w-140 flex-col gap-5 rounded-lg border border-border bg-surface p-9">
        <div className="flex size-14 items-center justify-center rounded-full bg-status-warning-bg text-status-warning-fg">
          <Icon name="lock" size={28} />
        </div>
        <div className="flex flex-col gap-2">
          <h1 id="titulo-restrito" className="text-heading font-semibold text-text">
            Acesso restrito
          </h1>
          <p className="m-0 text-body text-text-secondary">
            Este documento está vinculado a outro médico solicitante. Você só pode visualizar documentos vinculados ao seu
            CRM.
          </p>
        </div>
        <dl className="m-0 flex flex-col gap-2.5 rounded-md border border-border-subtle bg-subtle px-4 py-3.5">
          {linhas.map(([rotulo, valor]) => (
            <div key={rotulo} className="flex gap-4 text-sm leading-normal">
              <dt className="w-42.5 shrink-0 text-text-secondary">{rotulo}</dt>
              <dd className="m-0 font-mono break-all text-text">{valor}</dd>
            </div>
          ))}
        </dl>
        <div className="flex flex-wrap gap-2.5">
          <Button onClick={() => navigate('/meus-documentos')}>Voltar para meus documentos</Button>
          <Button
            variant="secondary"
            onClick={() => {
              sair()
              navigate('/login', { replace: true })
            }}
          >
            Entrar com outra conta
          </Button>
        </div>
      </section>
    </div>
  )
}
