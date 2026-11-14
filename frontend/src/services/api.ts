import type {
  CriarTriagemArquivoRequest,
  CriarTriagemTextoRequest,
  ErroEnvelope,
  EventoHistorico,
  HealthResponse,
  StatusTriagemResponse,
  TriagemCriadaResponse,
} from '../types/api'
import type { TriagemMediFlow } from '../types/clinical'

import { ApiError } from './erros'
import * as simulada from './apiSimulada'

export { ApiError }

/** Vazio = mesma origem (em dev, o proxy do Vite encaminha /api para o FastAPI). */
const BASE_URL = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')

function ehEnvelope(valor: unknown): valor is ErroEnvelope {
  return (
    typeof valor === 'object' &&
    valor !== null &&
    typeof (valor as ErroEnvelope).codigo === 'string' &&
    typeof (valor as ErroEnvelope).mensagem === 'string'
  )
}

async function requisitar<T>(caminho: string, init?: RequestInit): Promise<T> {
  let resposta: Response
  try {
    resposta = await fetch(`${BASE_URL}${caminho}`, init)
  } catch {
    throw new ApiError(0, 'REDE', 'Não foi possível conectar à API. Verifique se o servidor está no ar.')
  }

  const corpo: unknown = await resposta.json().catch(() => null)

  if (!resposta.ok) {
    if (ehEnvelope(corpo)) {
      throw new ApiError(resposta.status, corpo.codigo, corpo.mensagem, corpo.detalhes)
    }
    throw new ApiError(resposta.status, 'ERRO_REQUISICAO', `Falha na requisição (HTTP ${resposta.status}).`)
  }

  if (corpo === null) {
    throw new ApiError(resposta.status, 'RESPOSTA_INVALIDA', 'A API devolveu uma resposta inválida.')
  }
  return corpo as T
}

/** Modo demo (`VITE_USAR_FIXTURES=true`): as chamadas vão para um simulador local, sem backend. */
function modoDemo(): boolean {
  return import.meta.env.VITE_USAR_FIXTURES === 'true'
}

export function health(): Promise<HealthResponse> {
  if (modoDemo()) return simulada.health()
  return requisitar<HealthResponse>('/api/v1/health')
}

/** Envia um documento (PDF, imagem ou TXT) como multipart/form-data. */
export function submeterTriagemArquivo(dados: CriarTriagemArquivoRequest): Promise<TriagemCriadaResponse> {
  if (modoDemo()) return simulada.submeterTriagemArquivo(dados)
  const form = new FormData()
  form.append('file', dados.file)
  if (dados.documento_id) form.append('documento_id', dados.documento_id)
  if (dados.canal_origem) form.append('canal_origem', dados.canal_origem)
  return requisitar<TriagemCriadaResponse>('/api/v1/triagens', { method: 'POST', body: form })
}

/** Envia texto clínico como JSON. */
export function submeterTriagemTexto(dados: CriarTriagemTextoRequest): Promise<TriagemCriadaResponse> {
  if (modoDemo()) return simulada.submeterTriagemTexto(dados)
  return requisitar<TriagemCriadaResponse>('/api/v1/triagens', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tipo_arquivo: 'TEXTO', ...dados }),
  })
}

const caminhoTriagem = (documentoId: string) => `/api/v1/triagens/${encodeURIComponent(documentoId)}`

/** Consulta leve para polling: estado atual e se a triagem já terminou. */
export function obterStatus(documentoId: string, sinal?: AbortSignal): Promise<StatusTriagemResponse> {
  if (modoDemo()) return simulada.obterStatus(documentoId)
  return requisitar<StatusTriagemResponse>(`${caminhoTriagem(documentoId)}/status`, { signal: sinal })
}

/** Linha do tempo de eventos de auditoria, em ordem cronológica. */
export function obterHistorico(documentoId: string, sinal?: AbortSignal): Promise<EventoHistorico[]> {
  if (modoDemo()) return simulada.obterHistorico(documentoId)
  return requisitar<EventoHistorico[]>(`${caminhoTriagem(documentoId)}/historico`, { signal: sinal })
}

/**
 * Resultado completo da triagem. Chamar só depois de `obterStatus` devolver `concluido`:
 * se ainda não houver resultado, a API executa o pipeline na hora.
 */
export function obterTriagem(documentoId: string, sinal?: AbortSignal): Promise<TriagemMediFlow> {
  if (modoDemo()) return simulada.obterTriagem(documentoId)
  return requisitar<TriagemMediFlow>(caminhoTriagem(documentoId), { signal: sinal })
}

/** Refaz só a gravação no OCI de uma triagem em ERRO_PERSISTENCIA, sem chamar o modelo de novo. */
export function reprocessarPersistencia(documentoId: string): Promise<TriagemMediFlow> {
  if (modoDemo()) return simulada.reprocessarPersistencia(documentoId)
  return requisitar<TriagemMediFlow>(`${caminhoTriagem(documentoId)}/reprocessar-persistencia`, { method: 'POST' })
}
