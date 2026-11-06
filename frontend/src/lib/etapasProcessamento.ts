import type { BadgeTone } from '../components/ui/Badge'
import type { StatusTriagem } from '../types/clinical'

/**
 * Etapas da tela de Processamento (Figma 02a/02b).
 *
 * A API só informa o status geral (RECEBIDO, PROCESSANDO e um estado final); não há evento por etapa.
 * Por isso as etapas 1, 2 e 8 seguem o status real, e as etapas 3 a 7 avançam só na tela
 * (`etapaVisual`), para mostrar movimento enquanto o servidor trabalha.
 */

export type EstadoEtapa = 'concluido' | 'andamento' | 'aguardando' | 'falhou'

export type Etapa = {
  numero: number
  titulo: string
  subtexto: string
  /** Subtexto em fonte mono (IDs e caminhos). */
  mono: boolean
  estado: EstadoEtapa
}

export const ROTULO_ESTADO_ETAPA: Record<EstadoEtapa, string> = {
  concluido: 'Concluído',
  andamento: 'Em andamento',
  aguardando: 'Aguardando',
  falhou: 'Falhou',
}

export const TOTAL_ETAPAS = 8
export const PRIMEIRA_ETAPA_VISUAL = 3
export const ULTIMA_ETAPA_VISUAL = 7
/** A cada quanto tempo o marcador visual passa para a etapa seguinte. */
export const INTERVALO_AVANCO_MS = 4000

const ETAPAS_BASE: ReadonlyArray<Pick<Etapa, 'titulo' | 'subtexto' | 'mono'>> = [
  { titulo: 'Requisição aceita', subtexto: 'POST /api/v1/triagens → 202 · ID gerado', mono: true },
  { titulo: 'Original salvo no OCI', subtexto: 'Documento original guardado no armazenamento', mono: false },
  { titulo: 'Leitura do conteúdo', subtexto: 'Texto enviado ao modelo multimodal (Gemini)', mono: false },
  { titulo: 'Classificação', subtexto: 'Tipo de documento, especialidade e prioridade', mono: false },
  { titulo: 'Extração e validação', subtexto: 'Dados estruturados validados no esquema v2.0', mono: false },
  { titulo: 'Qualidade e conflitos', subtexto: 'Campos ausentes, incertos, conflitos e score combinado', mono: false },
  { titulo: 'Decisão de roteamento', subtexto: 'Regras de negócio aplicadas pelo grafo de decisão', mono: false },
  { titulo: 'Resultado salvo', subtexto: 'Decisão e dados extraídos gravados no OCI', mono: false },
]

export type EntradaEtapas = {
  /** Status mais recente da API; `null` antes da primeira resposta. */
  status: StatusTriagem | null
  /** Etapa (3 a 7) onde o marcador visual está durante o PROCESSANDO. */
  etapaVisual?: number
  /** `armazenamento_oci.caminho_objeto` do resultado, quando já conhecido. */
  caminhoResultado?: string | null
}

export type ProgressoProcessamento = {
  etapas: Etapa[]
  concluidas: number
  /** 0 a 100, a partir das etapas concluídas. */
  porcentagem: number
  rotuloBarra: string
  /** `true` quando o status é terminal e o polling pode parar. */
  terminal: boolean
}

export const ROTULO_BARRA_ANDAMENTO = 'Consultando o status a cada 2 s'

/** Etapa visual a mostrar depois de `ms` milissegundos em PROCESSANDO (limitada de 3 a 7). */
export function etapaVisualPorTempo(ms: number): number {
  const avancos = Math.floor(Math.max(0, ms) / INTERVALO_AVANCO_MS)
  return Math.min(ULTIMA_ETAPA_VISUAL, PRIMEIRA_ETAPA_VISUAL + avancos)
}

function limitarEtapaVisual(valor: number | undefined): number {
  if (valor === undefined) return PRIMEIRA_ETAPA_VISUAL
  return Math.min(ULTIMA_ETAPA_VISUAL, Math.max(PRIMEIRA_ETAPA_VISUAL, Math.round(valor)))
}

/** Estado de cada uma das 8 etapas (índice 0 = etapa 1). */
function estadosPorStatus(status: StatusTriagem | null, etapaVisual: number): EstadoEtapa[] {
  const todas = (estado: EstadoEtapa) => Array<EstadoEtapa>(TOTAL_ETAPAS).fill(estado)
  const ate = (fim: number, restante: EstadoEtapa): EstadoEtapa[] =>
    ETAPAS_BASE.map((_, i) => (i + 1 <= fim ? 'concluido' : restante))

  switch (status) {
    case 'PROCESSADO':
    case 'EM_REVISAO':
      return todas('concluido')

    case 'PROCESSANDO': {
      const estados = ate(etapaVisual - 1, 'aguardando')
      estados[etapaVisual - 1] = 'andamento'
      return estados
    }

    case 'ERRO_PROCESSAMENTO': {
      // A API não diz em qual etapa falhou: marcamos a que estava em andamento na tela.
      const estados = ate(etapaVisual - 1, 'aguardando')
      estados[etapaVisual - 1] = 'falhou'
      return estados
    }

    case 'ERRO_PERSISTENCIA': {
      // A decisão clínica foi calculada; só a gravação final do resultado falhou.
      const estados = ate(TOTAL_ETAPAS - 1, 'aguardando')
      estados[TOTAL_ETAPAS - 1] = 'falhou'
      return estados
    }

    case 'RECEBIDO':
    case null:
    default: {
      // Aceito e na fila: o original ainda está sendo guardado.
      const estados = ate(1, 'aguardando')
      estados[1] = 'andamento'
      return estados
    }
  }
}

function rotuloBarraDe(status: StatusTriagem | null): string {
  switch (status) {
    case 'PROCESSADO':
    case 'EM_REVISAO':
      return 'Triagem concluída'
    case 'ERRO_PROCESSAMENTO':
    case 'ERRO_PERSISTENCIA':
      return 'Triagem interrompida'
    default:
      return ROTULO_BARRA_ANDAMENTO
  }
}

export function statusTerminal(status: StatusTriagem | null): boolean {
  return (
    status === 'PROCESSADO' ||
    status === 'EM_REVISAO' ||
    status === 'ERRO_PROCESSAMENTO' ||
    status === 'ERRO_PERSISTENCIA'
  )
}

export function derivarEtapas({ status, etapaVisual, caminhoResultado }: EntradaEtapas): ProgressoProcessamento {
  const estados = estadosPorStatus(status, limitarEtapaVisual(etapaVisual))

  const etapas = ETAPAS_BASE.map((base, indice): Etapa => {
    const ehResultado = indice === TOTAL_ETAPAS - 1
    const temCaminho = ehResultado && Boolean(caminhoResultado)
    return {
      numero: indice + 1,
      titulo: base.titulo,
      subtexto: temCaminho ? (caminhoResultado as string) : base.subtexto,
      mono: base.mono || temCaminho,
      estado: estados[indice],
    }
  })

  const concluidas = estados.filter((e) => e === 'concluido').length
  return {
    etapas,
    concluidas,
    porcentagem: Math.round((concluidas / TOTAL_ETAPAS) * 100),
    rotuloBarra: rotuloBarraDe(status),
    terminal: statusTerminal(status),
  }
}

export type BadgeDoStatus = { tom: BadgeTone; rotulo: string }

/** Badge do cabeçalho do card (Figma: Info "PROCESSANDO" e Sucesso "PROCESSADO"). */
export function badgeDoStatus(status: StatusTriagem | null): BadgeDoStatus {
  switch (status) {
    case 'PROCESSADO':
      return { tom: 'success', rotulo: 'PROCESSADO' }
    case 'EM_REVISAO':
      return { tom: 'warning', rotulo: 'EM REVISÃO' }
    case 'ERRO_PROCESSAMENTO':
      return { tom: 'error', rotulo: 'ERRO NO PROCESSAMENTO' }
    case 'ERRO_PERSISTENCIA':
      return { tom: 'error', rotulo: 'ERRO AO SALVAR' }
    case 'PROCESSANDO':
      return { tom: 'info', rotulo: 'PROCESSANDO' }
    default:
      return { tom: 'info', rotulo: 'RECEBIDO' }
  }
}
