import { lerRegistro, esquecerEnvios } from '../lib/registroTriagens'
import { linhaDe } from '../lib/filasTriagens'
import type { LinhaTriagem } from '../lib/filasTriagens'
import { normalizarTriagem } from '../lib/normalizarTriagem'
import { statusTerminal } from '../lib/etapasProcessamento'
import { ApiError, obterStatus, obterTriagem } from './api'

/**
 * Lista provisória de triagens. A API ainda não tem `GET /api/v1/triagens`; por isso lemos os IDs
 * enviados por este navegador e consultamos cada um. Quando o endpoint existir, esta função passa
 * a chamá-lo e o resto da tela não muda.
 *
 * - IDs que a API não conhece (404) saem do registro e da lista.
 * - Outras falhas de um item não derrubam a lista: o item some só desta vez.
 * - Se todos falharem por rede, o erro sobe para a tela.
 */
export async function listarTriagens(sinal?: AbortSignal): Promise<LinhaTriagem[]> {
  const registro = lerRegistro()
  const desconhecidos: string[] = []
  let falhasDeRede = 0

  const linhas = await Promise.all(
    registro.map(async (envio): Promise<LinhaTriagem | null> => {
      try {
        const { status, concluido } = await obterStatus(envio.documentoId, sinal)
        const terminou = concluido || statusTerminal(status)
        const triagem = terminou ? normalizarTriagem(await obterTriagem(envio.documentoId, sinal)) : null
        return linhaDe(envio, status, triagem)
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) desconhecidos.push(envio.documentoId)
        else if (e instanceof ApiError && e.codigo === 'REDE') falhasDeRede += 1
        return null
      }
    }),
  )

  if (sinal?.aborted) return []
  esquecerEnvios(desconhecidos)
  if (registro.length > 0 && falhasDeRede === registro.length) {
    throw new ApiError(0, 'REDE', 'Não foi possível conectar à API. Verifique se o servidor está no ar.')
  }
  return linhas.filter((l): l is LinhaTriagem => l !== null)
}
