import { useId, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { CardsFila, FaixaMedico, TabelaTriagens } from '../components/triagens'
import { Button, Icon, Input } from '../components/ui'
import { useListaTriagens } from '../hooks/useListaTriagens'
import {
  buscarPorId,
  contadorDocumentos,
  contarFilas,
  ehDoMedicoLogado,
  filaDaUrl,
  FILAS_MEUS_DOCUMENTOS,
  FILAS_TRIAGENS,
  filtrarPorFila,
} from '../lib/filasTriagens'
import type { IdFila } from '../lib/filasTriagens'

type Variante = 'triagens' | 'meus'

const TEXTOS: Record<Variante, { titulo: string; subtitulo: string }> = {
  triagens: { titulo: 'Triagens e filas', subtitulo: 'Documentos enviados neste navegador, por status e destino.' },
  meus: { titulo: 'Meus documentos', subtitulo: 'Documentos em que você consta como médico solicitante.' },
}

const AVISO_REVISAO =
  'Fila lógica de revisão: os casos ficam listados para auditoria com o motivo. No MVP não há aprovar, rejeitar ou corrigir por esta tela.'

/** Telas 04a/04b (variante "triagens") e 04c (variante "meus"). */
export function ListaTriagensPage({ variante }: { variante: Variante }) {
  const idBusca = useId()
  const [parametros, setParametros] = useSearchParams()
  const [busca, setBusca] = useState('')
  const { estado, recarregar } = useListaTriagens()

  const fila = filaDaUrl(parametros.get('fila'))
  const filas = variante === 'meus' ? FILAS_MEUS_DOCUMENTOS : FILAS_TRIAGENS
  const textos = TEXTOS[variante]

  const base = useMemo(() => {
    if (estado.fase !== 'pronto') return []
    return variante === 'meus' ? estado.linhas.filter(ehDoMedicoLogado) : estado.linhas
  }, [estado, variante])
  const contagens = useMemo(() => contarFilas(base), [base])
  const daFila = useMemo(() => filtrarPorFila(base, fila), [base, fila])
  const visiveis = useMemo(() => buscarPorId(daFila, busca), [daFila, busca])

  function selecionarFila(id: IdFila) {
    setParametros(id === 'todos' ? {} : { fila: id }, { replace: true })
  }

  const filaAtual = filas.find((f) => f.id === fila) ?? filas[0]
  const vazio =
    base.length === 0 ? (
      variante === 'meus' ? (
        'Nenhum documento vinculado ao seu CRM entre os enviados neste navegador.'
      ) : (
        <>
          Nenhuma triagem enviada neste navegador ainda.{' '}
          <Link to="/nova-triagem" className="text-link hover:underline">
            Enviar uma triagem
          </Link>
        </>
      )
    ) : daFila.length === 0 ? (
      'Nenhum documento nesta fila.'
    ) : (
      'Nenhum documento com esse ID.'
    )

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col items-start gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex flex-col gap-1.5">
          <h1 className="text-heading font-semibold text-text">{textos.titulo}</h1>
          <p className="m-0 text-body text-text-secondary">{textos.subtitulo}</p>
        </div>
        <Link
          to="/nova-triagem"
          className="inline-flex h-11 shrink-0 items-center gap-2 rounded-md bg-primary px-4.5 text-base font-semibold text-on-primary transition-colors hover:bg-primary-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
        >
          <Icon name="plus" size={18} />
          Nova triagem
        </Link>
      </header>

      {variante === 'meus' && <FaixaMedico />}

      <CardsFila filas={filas} contagens={contagens} ativa={fila} onSelecionar={selecionarFila} />

      <section aria-labelledby="titulo-tabela" className="overflow-clip rounded-lg border border-border bg-surface">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border-subtle px-5 py-4.5">
          <div className="flex items-baseline gap-1.5">
            <h2 id="titulo-tabela" className="m-0 text-[17px] font-semibold text-text">
              {filaAtual.titulo}
            </h2>
            <span className="text-body text-text-secondary">{contadorDocumentos(visiveis.length)}</span>
          </div>
          <div className="flex w-full items-center gap-2 sm:w-auto">
            <label htmlFor={idBusca} className="text-sm text-text-secondary">
              Buscar ID
            </label>
            <Input
              id={idBusca}
              type="search"
              placeholder="DOC-CLIN-…"
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
              autoComplete="off"
              className="h-10 w-full rounded-sm sm:w-65"
            />
          </div>
        </div>

        {fila === 'revisao' && variante === 'triagens' && (
          <p className="m-0 border-b border-status-warning-border bg-status-warning-bg px-5 py-3 text-sm leading-normal text-status-warning-banner">
            {AVISO_REVISAO}
          </p>
        )}

        {estado.fase === 'carregando' ? (
          <p role="status" className="m-0 px-5 py-10 text-center text-text-secondary">
            Carregando triagens…
          </p>
        ) : estado.fase === 'erro' ? (
          <div role="alert" className="flex flex-col items-center gap-3 px-5 py-10 text-center">
            <p className="m-0 text-[15px] text-status-danger-fg">{estado.mensagem}</p>
            <Button variant="secondary" size="S" onClick={recarregar}>
              Tentar novamente
            </Button>
          </div>
        ) : (
          <TabelaTriagens linhas={visiveis} vazio={vazio} />
        )}
      </section>

      <p className="m-0 text-caption text-text-secondary">
        Lista provisória: a API ainda não lista triagens, então aparecem só os documentos enviados neste navegador.
      </p>
    </div>
  )
}
