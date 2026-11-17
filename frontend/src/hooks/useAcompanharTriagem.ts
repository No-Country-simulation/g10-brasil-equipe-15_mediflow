import { useCallback, useEffect, useState } from 'react'
import { etapaVisualPorTempo, PRIMEIRA_ETAPA_VISUAL, statusTerminal } from '../lib/etapasProcessamento'
import { mensagemDeErro } from '../lib/mensagensErro'
import { ApiError, obterHistorico, obterStatus, obterTriagem } from '../services/api'
import type { EventoHistorico } from '../types/api'
import type { StatusTriagem, TriagemMediFlow } from '../types/clinical'

/** Intervalo entre consultas de status (o Figma mostra "Consultando o status a cada 2 s"). */
export const INTERVALO_POLLING_MS = 2000
/** Falhas seguidas (rede ou 5xx) toleradas antes de mostrar erro. */
export const MAX_FALHAS_SEGUIDAS = 3
/** Frequência com que o marcador visual das etapas 3 a 7 confere se deve avançar. */
const TIQUE_ETAPA_VISUAL_MS = 1000

export type ErroAcompanhamento = { mensagem: string; codigo: string }

export type Acompanhamento = {
  /** `null` até a primeira resposta da API. */
  status: StatusTriagem | null
  /** Etapa (3 a 7) onde o marcador "Em andamento" está durante o PROCESSANDO. */
  etapaVisual: number
  historico: EventoHistorico[]
  /** Resultado completo; só é buscado depois que o status vira final. */
  resultado: TriagemMediFlow | null
  /** Horário do evento RECEBIDO do histórico (ISO), quando disponível. */
  enviadoEm: string | null
  /** Motivo registrado no histórico quando a triagem terminou em erro. */
  motivoErro: string | null
  erro: ErroAcompanhamento | null
  terminal: boolean
  /** Recomeça o acompanhamento depois de um erro. */
  tentarNovamente: () => void
}

type Estado = {
  chave: string
  status: StatusTriagem | null
  etapaVisual: number
  historico: EventoHistorico[]
  resultado: TriagemMediFlow | null
  erro: ErroAcompanhamento | null
}

function estadoInicial(chave: string): Estado {
  return { chave, status: null, etapaVisual: PRIMEIRA_ETAPA_VISUAL, historico: [], resultado: null, erro: null }
}

/** 4xx não melhora ao repetir (documento inexistente, ID inválido); rede e 5xx podem ser transitórios. */
function falhaDefinitiva(erro: unknown): boolean {
  return erro instanceof ApiError && erro.status >= 400 && erro.status < 500
}

function motivoDoErro(historico: EventoHistorico[]): string | null {
  const evento = [...historico]
    .reverse()
    .find((e) => e.status_novo === 'ERRO_PROCESSAMENTO' || e.status_novo === 'ERRO_PERSISTENCIA')
  return evento?.motivo ?? null
}

/**
 * Acompanha uma triagem: consulta `/status` a cada 2 s até um estado final, lê o `/historico` quando
 * o status muda e busca o resultado completo uma única vez, só depois de concluída (a API executa o
 * pipeline na hora se o resultado for pedido antes).
 */
export function useAcompanharTriagem(documentoId: string | undefined): Acompanhamento {
  const [tentativa, setTentativa] = useState(0)
  // O estado carrega a chave a que pertence: ao trocar de documento ou tentar de novo, a chave muda
  // e o estado antigo é ignorado, sem precisar zerar tudo dentro de um efeito.
  const chave = `${documentoId ?? ''}#${tentativa}`
  const [guardado, setGuardado] = useState<Estado>(() => estadoInicial(chave))
  const { status, etapaVisual, historico, resultado, erro } = guardado.chave === chave ? guardado : estadoInicial(chave)

  const atualizar = useCallback(
    (daChave: string, parcial: Partial<Omit<Estado, 'chave'>>) =>
      setGuardado((anterior) => ({
        ...(anterior.chave === daChave ? anterior : estadoInicial(daChave)),
        ...parcial,
      })),
    [],
  )

  useEffect(() => {
    if (!documentoId) return

    const controle = new AbortController()
    const { signal } = controle
    let temporizador: ReturnType<typeof setTimeout> | undefined
    let ultimoStatus: StatusTriagem | null = null
    let falhasSeguidas = 0

    async function lerHistorico() {
      try {
        const eventos = await obterHistorico(documentoId as string, signal)
        if (!signal.aborted) atualizar(chave, { historico: eventos })
      } catch {
        // O histórico só complementa a tela (hora do envio e motivo de erro).
      }
    }

    async function lerResultado() {
      try {
        const triagem = await obterTriagem(documentoId as string, signal)
        if (!signal.aborted) atualizar(chave, { resultado: triagem })
      } catch {
        // O resultado só enriquece a tela; a página de Resultado o busca de novo.
      }
    }

    async function ciclo() {
      try {
        const resposta = await obterStatus(documentoId as string, signal)
        if (signal.aborted) return
        falhasSeguidas = 0
        atualizar(chave, { status: resposta.status })

        const mudou = resposta.status !== ultimoStatus
        ultimoStatus = resposta.status
        const terminou = resposta.concluido || statusTerminal(resposta.status)

        if (mudou) await lerHistorico()
        if (terminou) {
          await lerResultado()
          return
        }
      } catch (e) {
        if (signal.aborted) return
        falhasSeguidas += 1
        if (falhaDefinitiva(e) || falhasSeguidas >= MAX_FALHAS_SEGUIDAS) {
          atualizar(chave, {
            erro: { mensagem: mensagemDeErro(e), codigo: e instanceof ApiError ? e.codigo : 'DESCONHECIDO' },
          })
          return
        }
      }
      if (!signal.aborted) temporizador = setTimeout(ciclo, INTERVALO_POLLING_MS)
    }

    void ciclo()

    return () => {
      controle.abort()
      clearTimeout(temporizador)
    }
  }, [documentoId, chave, atualizar])

  // Movimento visual das etapas 3 a 7 enquanto o servidor processa. Ao sair de PROCESSANDO o valor fica,
  // para que um erro aponte a etapa que estava em andamento.
  useEffect(() => {
    if (status !== 'PROCESSANDO') return
    const inicio = Date.now()
    const intervalo = setInterval(
      () => atualizar(chave, { etapaVisual: etapaVisualPorTempo(Date.now() - inicio) }),
      TIQUE_ETAPA_VISUAL_MS,
    )
    return () => clearInterval(intervalo)
  }, [status, chave, atualizar])

  const tentarNovamente = useCallback(() => setTentativa((n) => n + 1), [])

  return {
    status,
    etapaVisual,
    historico,
    resultado,
    enviadoEm: historico.find((e) => e.tipo_evento === 'RECEBIDO')?.criado_em ?? null,
    motivoErro: motivoDoErro(historico),
    erro,
    terminal: statusTerminal(status),
    tentarNovamente,
  }
}
