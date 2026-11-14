import { useCallback, useEffect, useState } from 'react'
import { statusTerminal } from '../lib/etapasProcessamento'
import { mensagemDeErro } from '../lib/mensagensErro'
import { normalizarTriagem } from '../lib/normalizarTriagem'
import { ApiError, obterHistorico, obterStatus, obterTriagem, reprocessarPersistencia } from '../services/api'
import type { EventoHistorico } from '../types/api'
import type { StatusTriagem, TriagemMediFlow } from '../types/clinical'

/** O histórico carrega à parte: se falhar, o resultado continua na tela. */
export type EstadoHistorico = { fase: 'ok'; eventos: EventoHistorico[] } | { fase: 'carregando' } | { fase: 'indisponivel' }

export type EstadoResultado =
  | { fase: 'carregando' }
  /** A triagem ainda não terminou: a página não pede o resultado (a API executaria o pipeline na hora). */
  | { fase: 'em_andamento'; status: StatusTriagem }
  | { fase: 'erro'; mensagem: string; codigo: string }
  | {
      fase: 'pronto'
      triagem: TriagemMediFlow
      /** Resposta da API como veio, para o painel "Ver JSON da resposta". */
      bruto: unknown
      historico: EstadoHistorico
    }

export type Reprocessamento = { fase: 'ocioso' } | { fase: 'enviando' } | { fase: 'erro'; mensagem: string }

type Guardado = { chave: string; estado: EstadoResultado }

function erroDe(e: unknown): EstadoResultado {
  return { fase: 'erro', mensagem: mensagemDeErro(e), codigo: e instanceof ApiError ? e.codigo : 'DESCONHECIDO' }
}

async function carregarHistorico(documentoId: string, signal?: AbortSignal): Promise<EstadoHistorico> {
  try {
    return { fase: 'ok', eventos: await obterHistorico(documentoId, signal) }
  } catch {
    return { fase: 'indisponivel' }
  }
}

/** Carrega o resultado completo e o histórico de uma triagem já concluída. */
export function useResultadoTriagem(documentoId: string | undefined) {
  const [versao, setVersao] = useState(0)
  const chave = `${documentoId ?? ''}#${versao}`
  const [guardado, setGuardado] = useState<Guardado>({ chave, estado: { fase: 'carregando' } })
  const [reprocessamento, setReprocessamento] = useState<Reprocessamento>({ fase: 'ocioso' })
  const estado: EstadoResultado = guardado.chave === chave ? guardado.estado : { fase: 'carregando' }

  useEffect(() => {
    if (!documentoId) return
    const controle = new AbortController()
    const { signal } = controle
    const definir = (novo: EstadoResultado) => {
      if (!signal.aborted) setGuardado({ chave, estado: novo })
    }

    void (async () => {
      try {
        const { status, concluido } = await obterStatus(documentoId, signal)
        if (!concluido && !statusTerminal(status)) {
          definir({ fase: 'em_andamento', status })
          return
        }
        const [bruto, historico] = await Promise.all([
          obterTriagem(documentoId, signal),
          carregarHistorico(documentoId, signal),
        ])
        definir({ fase: 'pronto', triagem: normalizarTriagem(bruto), bruto, historico })
      } catch (e) {
        if (signal.aborted) return
        definir(erroDe(e))
      }
    })()

    return () => controle.abort()
  }, [documentoId, chave])

  const recarregar = useCallback(() => setVersao((v) => v + 1), [])

  /** Tenta de novo só o histórico, sem recarregar o resultado. */
  const recarregarHistorico = useCallback(async () => {
    if (!documentoId) return
    const trocar = (historico: EstadoHistorico) =>
      setGuardado((g) =>
        g.chave === chave && g.estado.fase === 'pronto' ? { chave, estado: { ...g.estado, historico } } : g,
      )
    trocar({ fase: 'carregando' })
    trocar(await carregarHistorico(documentoId))
  }, [documentoId, chave])

  /** "Tentar salvar de novo" (03e): refaz a gravação no OCI e recarrega a página. */
  const reprocessar = useCallback(async () => {
    if (!documentoId) return
    setReprocessamento({ fase: 'enviando' })
    try {
      await reprocessarPersistencia(documentoId)
      setReprocessamento({ fase: 'ocioso' })
      setVersao((v) => v + 1)
    } catch (e) {
      setReprocessamento({ fase: 'erro', mensagem: mensagemDeErro(e) })
    }
  }, [documentoId])

  return { estado, recarregar, recarregarHistorico, reprocessar, reprocessamento }
}
