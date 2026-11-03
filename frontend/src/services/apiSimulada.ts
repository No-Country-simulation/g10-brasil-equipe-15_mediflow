/**
 * API simulada do modo demo (`VITE_USAR_FIXTURES=true`). Permite ver o fluxo inteiro sem backend e
 * sem chave do Gemini. As respostas finais vêm dos cenários da demo (`CENARIOS_DEMO`).
 *
 * Linha do tempo de cada triagem, contada a partir do envio:
 *   0 s  → RECEBIDO · 2 s → PROCESSANDO · 12 s → estado final do cenário (PROCESSADO ou EM_REVISAO)
 */
import { CENARIOS_DEMO } from '../fixtures'
import type { IdCenario } from '../fixtures'
import type {
  CriarTriagemArquivoRequest,
  CriarTriagemTextoRequest,
  EventoHistorico,
  HealthResponse,
  StatusTriagemResponse,
  TriagemCriadaResponse,
} from '../types/api'
import type { StatusTriagem, TriagemMediFlow } from '../types/clinical'
import { ApiError } from './erros'

export const ATRASO_ENVIO_MS = 400
export const INICIO_PROCESSANDO_MS = 2000
export const FIM_PROCESSANDO_MS = 12000

type Registro = { cenario: IdCenario; canal: string | null; enviadoEm: number }

const CHAVE_STORAGE = 'mediflow:demo:triagens'
const memoria = new Map<string, Registro>()

function lerArmazenado(): Record<string, Registro> {
  try {
    return JSON.parse(sessionStorage.getItem(CHAVE_STORAGE) ?? '{}') as Record<string, Registro>
  } catch {
    return {}
  }
}

/** Guarda também em sessionStorage para a triagem sobreviver a um F5; sem storage, só em memória. */
function salvar(id: string, registro: Registro) {
  memoria.set(id, registro)
  try {
    sessionStorage.setItem(CHAVE_STORAGE, JSON.stringify({ ...lerArmazenado(), [id]: registro }))
  } catch {
    // Sem sessionStorage (modo privado, por exemplo): continua só em memória.
  }
}

function buscar(id: string): Registro {
  const registro = memoria.get(id) ?? lerArmazenado()[id]
  if (!registro) {
    throw new ApiError(404, 'DOCUMENTO_NAO_ENCONTRADO', `Documento '${id}' não encontrado.`)
  }
  return registro
}

/** Esquece as triagens simuladas (usado nos testes). */
export function limparSimulacao() {
  memoria.clear()
  try {
    sessionStorage.removeItem(CHAVE_STORAGE)
  } catch {
    // ignora
  }
}

/** Escolhe o cenário pelo conteúdo enviado, que é o que os casos de teste da tela carregam. */
export function escolherCenario(nome: string, texto: string): IdCenario {
  const base = `${nome} ${texto}`.toLowerCase()
  if (base.includes('borda_score') || base.includes('lombalgia')) return 'ambiguo'
  if (base.includes('laudodeimagem_pdf') || base.includes('tromboembolismo')) return 'urgente'
  return 'rotina'
}

function gerarId(): string {
  const aleatorio = Array.from({ length: 8 }, () => Math.floor(Math.random() * 16).toString(16)).join('')
  return `DOC-DEMO-${aleatorio.toUpperCase()}`
}

const esperar = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms))

async function registrarEnvio(
  cenario: IdCenario,
  documentoId: string | undefined,
  canal: string | undefined,
): Promise<TriagemCriadaResponse> {
  await esperar(ATRASO_ENVIO_MS)
  const id = documentoId?.trim() || gerarId()
  salvar(id, { cenario, canal: canal ?? null, enviadoEm: Date.now() })
  return {
    documento_id: id,
    status: 'RECEBIDO',
    status_url: `/api/v1/triagens/${id}/status`,
    historico_url: `/api/v1/triagens/${id}/historico`,
    mensagem: 'Documento aceito e enfileirado para processamento (modo demo).',
  }
}

export async function submeterTriagemArquivo(dados: CriarTriagemArquivoRequest): Promise<TriagemCriadaResponse> {
  const ehTexto = dados.file.name.toLowerCase().endsWith('.txt')
  const conteudo = ehTexto ? await dados.file.text() : ''
  return registrarEnvio(escolherCenario(dados.file.name, conteudo), dados.documento_id, dados.canal_origem)
}

export function submeterTriagemTexto(dados: CriarTriagemTextoRequest): Promise<TriagemCriadaResponse> {
  return registrarEnvio(escolherCenario('', dados.documento_texto), dados.documento_id, dados.canal_origem)
}

function statusFinalDe(cenario: IdCenario): StatusTriagem {
  return CENARIOS_DEMO[cenario].status
}

function statusAgora(registro: Registro): StatusTriagem {
  const decorrido = Date.now() - registro.enviadoEm
  if (decorrido < INICIO_PROCESSANDO_MS) return 'RECEBIDO'
  if (decorrido < FIM_PROCESSANDO_MS) return 'PROCESSANDO'
  return statusFinalDe(registro.cenario)
}

export async function obterStatus(documentoId: string): Promise<StatusTriagemResponse> {
  const registro = buscar(documentoId)
  const status = statusAgora(registro)
  const concluido = status !== 'RECEBIDO' && status !== 'PROCESSANDO'
  const roteamento = CENARIOS_DEMO[registro.cenario].decisao_roteamento
  return {
    documento_id: documentoId,
    status,
    destinos: concluido ? (roteamento?.destinos ?? []) : [],
    requer_auditoria_humana: concluido ? (roteamento?.requer_auditoria_humana ?? false) : false,
    concluido,
  }
}

export async function obterHistorico(documentoId: string): Promise<EventoHistorico[]> {
  const registro = buscar(documentoId)
  const decorrido = Date.now() - registro.enviadoEm
  const final = statusFinalDe(registro.cenario)
  const justificativa = CENARIOS_DEMO[registro.cenario].decisao_roteamento?.justificativa_roteamento ?? null

  const evento = (
    tipo: string,
    ator: string,
    quando: number,
    anterior: StatusTriagem | null,
    novo: StatusTriagem,
    motivo: string | null,
  ): EventoHistorico => ({
    evento_id: `${documentoId}-${tipo}`,
    documento_id: documentoId,
    tipo_evento: tipo,
    criado_em: new Date(registro.enviadoEm + quando).toISOString(),
    ator,
    status_anterior: anterior,
    status_novo: novo,
    motivo,
    versao_esquema: '2.0.0',
  })

  const eventos = [evento('RECEBIDO', 'API_INGESTAO', 0, null, 'RECEBIDO', 'Documento aceito (modo demo)')]
  if (decorrido >= INICIO_PROCESSANDO_MS) {
    eventos.push(
      evento('PROCESSANDO', 'WORKFLOW_ENGINE', INICIO_PROCESSANDO_MS, 'RECEBIDO', 'PROCESSANDO', 'Iniciando extração e roteamento'),
    )
  }
  if (decorrido >= FIM_PROCESSANDO_MS) {
    eventos.push(evento('ROTEADO', 'LANGGRAPH_ROUTER', FIM_PROCESSANDO_MS, 'PROCESSANDO', final, justificativa))
  }
  return eventos
}

export async function obterTriagem(documentoId: string): Promise<TriagemMediFlow> {
  const registro = buscar(documentoId)
  const triagem = structuredClone(CENARIOS_DEMO[registro.cenario])
  triagem.documento_id = documentoId
  triagem.canal_origem = registro.canal
  return triagem
}

export async function health(): Promise<HealthResponse> {
  return { status: 'healthy', versao: 'demo', servicos: { api: 'simulada' } }
}
