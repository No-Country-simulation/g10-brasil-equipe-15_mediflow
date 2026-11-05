import type { BadgeTone } from '../components/ui/Badge'
import type { Conflito, Crm, Destino, Gravidade, StatusTriagem, TriagemMediFlow } from '../types/clinical'
import type { EventoHistorico } from '../types/api'
import { CAMPOS_OBRIGATORIOS, ROTULO_CAMPO, rotuloTipoDocumento } from './rotulos'

/** Regras de apresentação da tela de Resultado (Figma 03a–03e), sem React. */

const numero = (valor: number, casas = 2) => valor.toLocaleString('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas })
export const formatarScore = (valor: number) => numero(valor)

// ---------- Badge do cabeçalho ----------

/** No Resultado o badge mostra o código do status, como no Figma. */
export function tomDoStatus(status: StatusTriagem): BadgeTone {
  switch (status) {
    case 'PROCESSADO':
      return 'success'
    case 'EM_REVISAO':
      return 'warning'
    case 'ERRO_PROCESSAMENTO':
    case 'ERRO_PERSISTENCIA':
      return 'error'
    default:
      return 'info'
  }
}

// ---------- Campos extraídos ----------

export type SituacaoCampo =
  | { tipo: 'presente' }
  | { tipo: 'ausente'; exigeRevisao: boolean }
  | { tipo: 'incerto' }

/** Situação de um campo a partir de `qualidade` e do valor extraído. */
export function situacaoDoCampo(triagem: TriagemMediFlow, caminho: string, valor: unknown): SituacaoCampo {
  const qualidade = triagem.qualidade
  if (qualidade?.campos_incertos.includes(caminho)) return { tipo: 'incerto' }
  const vazio = valor === null || valor === undefined || valor === ''
  if (vazio || qualidade?.campos_ausentes.includes(caminho)) {
    return { tipo: 'ausente', exigeRevisao: CAMPOS_OBRIGATORIOS.has(caminho) }
  }
  return { tipo: 'presente' }
}

export function formatarCrm(crm: Crm | string | null | undefined): string | null {
  if (!crm) return null
  if (typeof crm === 'string') return crm
  if (!crm.numero) return null
  return crm.uf ? `${crm.numero} / ${crm.uf}` : crm.numero
}

export function formatarIdade(idade: number | null | undefined): string | null {
  if (idade === null || idade === undefined) return null
  return `${idade} ${idade === 1 ? 'ano' : 'anos'}`
}

export function formatarEspecialidade(especialidade: string[] | string | null | undefined): string | null {
  if (!especialidade) return null
  const lista = Array.isArray(especialidade) ? especialidade : [especialidade]
  return lista.length > 0 ? lista.join(', ') : null
}

// ---------- Conflitos e medicamentos ----------

export const TOM_GRAVIDADE: Record<Gravidade, 'danger' | 'warning' | 'neutral'> = {
  ALTA: 'danger',
  MEDIA: 'warning',
  BAIXA: 'neutral',
}

/** Conflitos que apontam para `medicamentos[indice]` (ex.: `medicamentos[0].dose`). */
export function conflitosDoMedicamento(conflitos: readonly Conflito[], indice: number): Conflito[] {
  const prefixo = `medicamentos[${indice}]`
  return conflitos.filter((c) => c.campos.some((campo) => campo.startsWith(prefixo)))
}

/** Rótulo curto da sinalização do medicamento a partir do tipo do conflito. */
export function rotuloSinalizacao(conflito: Conflito): string {
  const texto = conflito.tipo.replace(/_/g, ' ').toLowerCase()
  return texto.charAt(0).toUpperCase() + texto.slice(1)
}

// ---------- Confiança ----------

export type Confianca = {
  classificacao: number
  extracao: number
  combinado: number
  limiar: number
  abaixoDoLimiar: boolean
  /** Linha "combinado = mín(a; b) = c", só quando os números batem com essa regra. */
  formula: string | null
}

export function confiancaDe(triagem: TriagemMediFlow): Confianca | null {
  const q = triagem.qualidade
  if (!q) return null
  const classificacao = triagem.classificacao?.score_classificacao ?? 0
  const extracao = q.score_extracao
  const combinado = q.score_combinado
  const minimo = Math.min(classificacao, extracao)
  return {
    classificacao,
    extracao,
    combinado,
    limiar: q.limiar_aplicado,
    // RF-18: compara com "<", então exatamente no limiar não revisa.
    abaixoDoLimiar: combinado < q.limiar_aplicado,
    formula:
      Math.abs(minimo - combinado) < 0.005
        ? `combinado = mín(${numero(classificacao)}; ${numero(extracao)}) = ${numero(combinado)}`
        : null,
  }
}

// ---------- Destinos ----------

export const TOM_DESTINO: Record<Destino, 'success' | 'danger' | 'warning' | 'info'> = {
  PRONTUARIO_ELETRONICO: 'success',
  FILA_URGENCIA_MEDICA: 'danger',
  FILA_REVISAO_HUMANA: 'warning',
  FARMACIA_HOSPITALAR: 'info',
  AUDITORIA_AUTORIZACOES: 'info',
}

// ---------- Banners ----------

export type Banner =
  | { tipo: 'sucesso'; titulo: string; corpo: string }
  | { tipo: 'urgente'; titulo: string; corpo: string; nota: string | null }
  | { tipo: 'revisao'; titulo: string; itens: string[]; nota: string }

export const NOTA_REVISAO =
  'No MVP a fila é lógica: o caso fica listado para auditoria, sem aprovar ou rejeitar por esta tela.'

function rotuloDoCampo(caminho: string): string {
  return ROTULO_CAMPO[caminho] ?? caminho
}

const TIPOS_FORA_DA_TAXONOMIA: ReadonlySet<string> = new Set(['OUTRO', 'NAO_IDENTIFICADO'])

export const MOTIVO_REVISAO_GENERICO = 'Caso sinalizado para revisão humana pela decisão de roteamento.'

/**
 * Motivos da revisão humana, na ordem do Figma: ausências, incertezas, conflitos e score.
 * Depois vêm os demais gatilhos da RN-08 (tipo fora da taxonomia, prioridade e urgência
 * indeterminadas). Sem nenhum motivo reconhecido, usa a justificativa do roteamento ou,
 * na falta dela, um texto genérico — a lista nunca fica vazia.
 */
export function motivosDaRevisao(triagem: TriagemMediFlow): string[] {
  const itens = motivosDeQualidade(triagem)
  const c = triagem.classificacao

  // Só OUTRO e NAO_IDENTIFICADO: o backend aceita apelidos de tipo que o front não traduz.
  if (c && TIPOS_FORA_DA_TAXONOMIA.has(c.tipo_documento)) {
    itens.push(`Tipo de documento fora da taxonomia (${rotuloTipoDocumento(c.tipo_documento)})`)
  }
  if (c?.nivel_prioridade === 'NAO_IDENTIFICADA') {
    itens.push('Prioridade não identificada')
  }
  // Com prioridade ausente ou NAO_IDENTIFICADA, o normalizador pode ter deduzido INDETERMINADO
  // sem o campo vir da API; nesse caso o motivo de prioridade já cobre o gatilho.
  if (c && c.nivel_prioridade !== 'NAO_IDENTIFICADA' && triagem.dados_extraidos?.urgencia === 'INDETERMINADO') {
    itens.push('Urgência clínica indeterminada')
  }

  if (itens.length === 0) {
    itens.push(triagem.decisao_roteamento?.justificativa_roteamento || MOTIVO_REVISAO_GENERICO)
  }
  return itens
}

function motivosDeQualidade(triagem: TriagemMediFlow): string[] {
  const q = triagem.qualidade
  if (!q) return []
  const itens = [
    ...q.campos_ausentes
      .filter((c) => CAMPOS_OBRIGATORIOS.has(c))
      .map((c) => `${rotuloDoCampo(c)} não consta no documento`),
    ...q.campos_incertos.map((c) => `${rotuloDoCampo(c)} incerto ou ilegível`),
    ...q.conflitos
      .filter((c) => c.gravidade !== 'BAIXA')
      .map((c) => `Conflito de gravidade ${c.gravidade === 'ALTA' ? 'alta' : 'média'}: ${c.descricao}`),
  ]
  const confianca = confiancaDe(triagem)
  if (confianca?.abaixoDoLimiar) {
    itens.push(`Score combinado ${numero(confianca.combinado)} abaixo do limiar ${numero(confianca.limiar)}`)
  }
  return itens
}

export function ehUrgente(triagem: TriagemMediFlow): boolean {
  return (
    triagem.classificacao?.nivel_prioridade === 'URGENTE' ||
    (triagem.decisao_roteamento?.destinos ?? []).includes('FILA_URGENCIA_MEDICA')
  )
}

export function emRevisao(triagem: TriagemMediFlow): boolean {
  return triagem.status === 'EM_REVISAO' || triagem.decisao_roteamento?.requer_auditoria_humana === true
}

// ---------- Alerta simulado (RF-22 e seção 12) ----------

export type SituacaoAlerta =
  | { tipo: 'registrado'; canal: string }
  /** Caso urgente cujo evento de alerta não foi registrado; o encaminhamento urgente continua. */
  | { tipo: 'falhou'; status: string | null }
  | { tipo: 'nenhum' }

/** Status de notificação que indicam falha (ex.: FALHA, FALHA_REGISTRO, ERRO_OCI). */
const STATUS_FALHA_ALERTA = /^(FALHA|ERRO)/i

/** A falha de alerta só existe em caso urgente: fora dele, nenhum alerta é devido. */
export function situacaoDoAlerta(triagem: TriagemMediFlow): SituacaoAlerta {
  const n = triagem.decisao_roteamento?.notificacao
  const statusFalho = n ? STATUS_FALHA_ALERTA.test(n.status) : false
  if (n?.gerada && !statusFalho) return { tipo: 'registrado', canal: n.canal }
  if (ehUrgente(triagem)) return { tipo: 'falhou', status: statusFalho ? (n?.status ?? null) : null }
  return { tipo: 'nenhum' }
}

export function textoFalhaAlerta(status: string | null): string {
  const detalhe = status ? ` (status ${status})` : ''
  return `Falha ao registrar o evento de alerta simulado${detalhe}. O encaminhamento à fila de urgência foi mantido.`
}

/** Banners do topo da página. Em 03c (urgente + revisão) vêm os dois, nessa ordem. */
export function bannersDe(triagem: TriagemMediFlow): Banner[] {
  if (triagem.status === 'ERRO_PROCESSAMENTO' || triagem.status === 'ERRO_PERSISTENCIA') return []
  const justificativa = triagem.decisao_roteamento?.justificativa_roteamento ?? ''
  const banners: Banner[] = []

  if (ehUrgente(triagem)) {
    const alerta = situacaoDoAlerta(triagem)
    banners.push({
      tipo: 'urgente',
      titulo: 'Urgente · encaminhado à fila de urgência médica',
      corpo: triagem.dados_extraidos?.achados_criticos || justificativa,
      nota:
        alerta.tipo === 'registrado'
          ? `Alerta registrado como evento simulado (${alerta.canal}). Nenhuma mensagem foi enviada a serviço externo.`
          : alerta.tipo === 'falhou'
            ? textoFalhaAlerta(alerta.status)
            : null,
    })
  }
  if (emRevisao(triagem)) {
    banners.push({
      tipo: 'revisao',
      titulo: 'Em revisão · encaminhado à fila de revisão humana',
      itens: motivosDaRevisao(triagem),
      nota: NOTA_REVISAO,
    })
  }
  if (banners.length === 0) {
    banners.push({ tipo: 'sucesso', titulo: 'Processado · encaminhado automaticamente', corpo: justificativa })
  }
  return banners
}

// ---------- Alerta de erro (03e) ----------

export type AlertaErro = {
  titulo: string
  corpo: string
  codigo: string
  podeReprocessar: boolean
}

export function alertaDeErro(triagem: TriagemMediFlow): AlertaErro | null {
  const detalhe = triagem.erro?.mensagem ? ` ${triagem.erro.mensagem}` : ''
  if (triagem.status === 'ERRO_PERSISTENCIA') {
    return {
      titulo: 'Triagem não confirmada · falha ao salvar o resultado',
      corpo:
        'O documento foi analisado, mas o resultado não pôde ser salvo no OCI Object Storage. Por isso a triagem não é dada como concluída.',
      codigo: `Etapa: persistencia_resultado · código ${triagem.erro?.codigo ?? 'ERRO_PERSISTENCIA'}${detalhe ? ` ·${detalhe}` : ''}`,
      podeReprocessar: true,
    }
  }
  if (triagem.status === 'ERRO_PROCESSAMENTO') {
    return {
      titulo: 'Triagem não concluída · falha no processamento',
      corpo: 'O documento não pôde ser analisado. Envie o documento de novo ou tente mais tarde.',
      codigo: `código ${triagem.erro?.codigo ?? 'ERRO_PROCESSAMENTO'}${detalhe ? ` ·${detalhe}` : ''}`,
      podeReprocessar: false,
    }
  }
  return null
}

// ---------- Histórico ----------

/**
 * Eventos em ordem cronológica por `criado_em` (seção 11.8), sem confiar na ordem da API.
 * A ordenação é estável; datas inválidas vão para o fim, na ordem em que chegaram.
 */
export function ordenarHistorico(eventos: readonly EventoHistorico[]): EventoHistorico[] {
  const instante = (e: EventoHistorico) => {
    const t = Date.parse(e.criado_em)
    return Number.isNaN(t) ? Number.POSITIVE_INFINITY : t
  }
  return [...eventos].sort((a, b) => {
    const ta = instante(a)
    const tb = instante(b)
    return ta === tb ? 0 : ta < tb ? -1 : 1
  })
}
