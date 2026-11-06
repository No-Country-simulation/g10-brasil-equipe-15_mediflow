import type { BadgeTone } from '../components/ui/Badge'
import type { Conflito, Crm, Destino, Gravidade, StatusTriagem, TriagemMediFlow } from '../types/clinical'
import { CAMPOS_OBRIGATORIOS, ROTULO_CAMPO } from './rotulos'

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

/** Motivos da revisão humana, na ordem do Figma: ausências, incertezas, conflitos e score. */
export function motivosDaRevisao(triagem: TriagemMediFlow): string[] {
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

/** Banners do topo da página. Em 03c (urgente + revisão) vêm os dois, nessa ordem. */
export function bannersDe(triagem: TriagemMediFlow): Banner[] {
  if (triagem.status === 'ERRO_PROCESSAMENTO' || triagem.status === 'ERRO_PERSISTENCIA') return []
  const justificativa = triagem.decisao_roteamento?.justificativa_roteamento ?? ''
  const notificacao = triagem.decisao_roteamento?.notificacao
  const banners: Banner[] = []

  if (ehUrgente(triagem)) {
    banners.push({
      tipo: 'urgente',
      titulo: 'Urgente · encaminhado à fila de urgência médica',
      corpo: triagem.dados_extraidos?.achados_criticos || justificativa,
      nota: notificacao?.gerada
        ? `Alerta registrado como evento simulado (${notificacao.canal}). Nenhuma mensagem foi enviada a serviço externo.`
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
