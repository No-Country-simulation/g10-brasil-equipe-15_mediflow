/** DTOs de transporte da API REST (espelho de src/api/schemas.py). */

import type { StatusTriagem } from './clinical'

/** Corpo JSON de POST /api/v1/triagens para envio de texto. */
export interface CriarTriagemTextoRequest {
  documento_id?: string
  tipo_arquivo?: string
  documento_texto: string
  canal_origem?: string
  metadados?: Record<string, unknown>
}

/** Campos do multipart de POST /api/v1/triagens para envio de arquivo. */
export interface CriarTriagemArquivoRequest {
  file: File
  documento_id?: string
  canal_origem?: string
}

/** Resposta 202 da submissão. */
export interface TriagemCriadaResponse {
  documento_id: string
  status: string
  status_url: string
  historico_url: string
  mensagem: string
}

export interface StatusTriagemResponse {
  documento_id: string
  status: StatusTriagem
  destinos: string[]
  requer_auditoria_humana: boolean
  concluido: boolean
}

export interface EventoHistorico {
  evento_id: string
  documento_id: string
  tipo_evento: string
  criado_em: string
  ator: string
  status_anterior?: string | null
  status_novo: string
  motivo?: string | null
  versao_esquema: string
}

export interface HealthResponse {
  status: string
  versao: string
  servicos: Record<string, string>
}

/** Envelope padronizado de erro devolvido pela API. */
export interface ErroEnvelope {
  codigo: string
  mensagem: string
  detalhes?: unknown
}
