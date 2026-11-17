import { useCallback, useEffect, useState } from 'react'
import type { LinhaTriagem } from '../lib/filasTriagens'
import { mensagemDeErro } from '../lib/mensagensErro'
import { listarTriagens } from '../services/listarTriagens'

/** Atualização automática enquanto houver triagem em andamento. */
export const INTERVALO_ATUALIZACAO_MS = 5000

export type EstadoLista =
  | { fase: 'carregando' }
  | { fase: 'erro'; mensagem: string }
  | { fase: 'pronto'; linhas: LinhaTriagem[] }

type Guardado = { chave: number; estado: EstadoLista }

export function useListaTriagens() {
  const [versao, setVersao] = useState(0)
  const [guardado, setGuardado] = useState<Guardado>({ chave: 0, estado: { fase: 'carregando' } })
  // Recarregar manualmente mostra "carregando"; a atualização automática mantém a lista na tela.
  const estado: EstadoLista = guardado.chave === versao || guardado.estado.fase === 'pronto' ? guardado.estado : { fase: 'carregando' }

  useEffect(() => {
    const controle = new AbortController()
    let temporizador: ReturnType<typeof setTimeout> | undefined

    async function carregar() {
      try {
        const linhas = await listarTriagens(controle.signal)
        if (controle.signal.aborted) return
        setGuardado({ chave: versao, estado: { fase: 'pronto', linhas } })
        if (linhas.some((l) => !l.concluida)) temporizador = setTimeout(carregar, INTERVALO_ATUALIZACAO_MS)
      } catch (e) {
        if (!controle.signal.aborted) setGuardado({ chave: versao, estado: { fase: 'erro', mensagem: mensagemDeErro(e) } })
      }
    }
    void carregar()

    return () => {
      controle.abort()
      clearTimeout(temporizador)
    }
  }, [versao])

  const recarregar = useCallback(() => setVersao((v) => v + 1), [])
  return { estado, recarregar }
}
