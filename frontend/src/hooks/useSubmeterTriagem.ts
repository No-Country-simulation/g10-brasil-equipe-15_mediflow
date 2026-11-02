import { useCallback, useRef, useState } from 'react'
import { mensagemDeErro } from '../lib/mensagensErro'
import { submeterTriagemArquivo, submeterTriagemTexto } from '../services/api'
import type { TriagemCriadaResponse } from '../types/api'

export type EntradaTriagem =
  | { tipo: 'arquivo'; arquivo: File; canalOrigem: string; documentoId?: string }
  | { tipo: 'texto'; texto: string; canalOrigem: string; documentoId?: string }

export type EstadoEnvio =
  | { fase: 'ocioso' }
  | { fase: 'enviando' }
  | { fase: 'sucesso'; resposta: TriagemCriadaResponse }
  | { fase: 'erro'; mensagem: string }

/** Controla o envio de uma triagem (arquivo ou texto) e expõe o estado para a interface. */
export function useSubmeterTriagem() {
  const [estado, setEstado] = useState<EstadoEnvio>({ fase: 'ocioso' })
  // Impede envio duplicado mesmo antes da próxima renderização (duplo clique).
  const emAndamento = useRef(false)

  /** Devolve `true` quando a API aceitou o documento (202). */
  const submeter = useCallback(async (entrada: EntradaTriagem): Promise<boolean> => {
    if (emAndamento.current) return false
    emAndamento.current = true
    setEstado({ fase: 'enviando' })

    const documentoId = entrada.documentoId?.trim() || undefined
    try {
      const resposta =
        entrada.tipo === 'arquivo'
          ? await submeterTriagemArquivo({
              file: entrada.arquivo,
              canal_origem: entrada.canalOrigem,
              documento_id: documentoId,
            })
          : await submeterTriagemTexto({
              documento_texto: entrada.texto,
              canal_origem: entrada.canalOrigem,
              documento_id: documentoId,
            })
      setEstado({ fase: 'sucesso', resposta })
      return true
    } catch (erro) {
      setEstado({ fase: 'erro', mensagem: mensagemDeErro(erro) })
      return false
    } finally {
      emAndamento.current = false
    }
  }, [])

  const reiniciar = useCallback(() => setEstado({ fase: 'ocioso' }), [])

  return { estado, submeter, reiniciar }
}
