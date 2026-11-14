import type { Crm, Destino, NivelPrioridade, StatusTriagem, TipoDocumento, TriagemMediFlow } from '../types/clinical'
import { MEDICO_LOGADO } from './medicoLogado'
import { formatarScore } from './resultadoTriagem'

/** Regras da tela "Triagens e filas" (Figma 04a–04c), sem React. */

/** Uma linha da tabela. Campos do resultado ficam `null` enquanto a triagem não termina. */
export type LinhaTriagem = {
  documentoId: string
  canal: string | null
  /** ISO 8601 */
  enviadoEm: string
  status: StatusTriagem
  concluida: boolean
  tipo: string | null
  prioridade: NivelPrioridade | null
  destinos: Destino[]
  requerRevisao: boolean
  score: number | null
  limiar: number | null
  crmMedico: Crm | string | null
}

export function linhaDe(
  base: { documentoId: string; canal: string | null; enviadoEm: string },
  status: StatusTriagem,
  triagem: TriagemMediFlow | null,
): LinhaTriagem {
  const r = triagem?.decisao_roteamento
  return {
    ...base,
    canal: triagem?.canal_origem ?? base.canal,
    status,
    concluida: triagem !== null,
    tipo: triagem?.classificacao?.tipo_documento ?? null,
    prioridade: triagem?.classificacao?.nivel_prioridade ?? null,
    destinos: r?.destinos.length ? r.destinos : r?.destino_principal ? [r.destino_principal] : [],
    requerRevisao: r?.requer_auditoria_humana ?? false,
    score: triagem?.qualidade?.score_combinado ?? null,
    limiar: triagem?.qualidade?.limiar_aplicado ?? null,
    crmMedico: triagem?.dados_extraidos?.medico.crm ?? null,
  }
}

// ---------- Filas ----------

export type IdFila = 'todos' | 'urgencia' | 'revisao' | 'processados' | 'andamento' | 'erro'

export const IDS_FILA: readonly IdFila[] = ['todos', 'urgencia', 'revisao', 'processados', 'andamento', 'erro']

export type Fila = {
  id: IdFila
  /** Rótulo do card de contagem. */
  rotulo: string
  /** Título da tabela quando a fila está ativa. */
  titulo: string
  /** Cor do número do card. */
  cor: string
}

const PREDICADOS: Record<IdFila, (l: LinhaTriagem) => boolean> = {
  todos: () => true,
  urgencia: (l) => l.prioridade === 'URGENTE' || l.destinos.includes('FILA_URGENCIA_MEDICA'),
  revisao: (l) => l.status === 'EM_REVISAO' || l.requerRevisao,
  processados: (l) => l.status === 'PROCESSADO',
  andamento: (l) => l.status === 'RECEBIDO' || l.status === 'PROCESSANDO',
  erro: (l) => l.status === 'ERRO_PROCESSAMENTO' || l.status === 'ERRO_PERSISTENCIA',
}

const COR: Record<IdFila, string> = {
  todos: 'text-text',
  urgencia: 'text-status-danger-fg',
  revisao: 'text-status-warning-fg',
  processados: 'text-status-success-fg',
  andamento: 'text-status-info-fg',
  erro: 'text-status-error-fg',
}

/** Rótulos de 04a/04b. */
export const FILAS_TRIAGENS: readonly Fila[] = [
  { id: 'todos', rotulo: 'Todos', titulo: 'Todas as triagens', cor: COR.todos },
  { id: 'urgencia', rotulo: 'Fila de urgência', titulo: 'Fila de urgência médica', cor: COR.urgencia },
  { id: 'revisao', rotulo: 'Fila de revisão', titulo: 'Fila de revisão humana', cor: COR.revisao },
  { id: 'processados', rotulo: 'Processados', titulo: 'Processados', cor: COR.processados },
  { id: 'andamento', rotulo: 'Em andamento', titulo: 'Em andamento', cor: COR.andamento },
  { id: 'erro', rotulo: 'Com erro', titulo: 'Com erro', cor: COR.erro },
]

/** Rótulos de 04c. */
export const FILAS_MEUS_DOCUMENTOS: readonly Fila[] = [
  { id: 'todos', rotulo: 'Meus documentos', titulo: 'Meus documentos', cor: COR.todos },
  { id: 'urgencia', rotulo: 'Urgentes', titulo: 'Urgentes', cor: COR.urgencia },
  { id: 'revisao', rotulo: 'Em revisão', titulo: 'Em revisão', cor: COR.revisao },
  { id: 'processados', rotulo: 'Processados', titulo: 'Processados', cor: COR.processados },
  { id: 'andamento', rotulo: 'Em andamento', titulo: 'Em andamento', cor: COR.andamento },
  { id: 'erro', rotulo: 'Com erro', titulo: 'Com erro', cor: COR.erro },
]

export function filaDaUrl(valor: string | null): IdFila {
  return IDS_FILA.includes(valor as IdFila) ? (valor as IdFila) : 'todos'
}

export function filtrarPorFila(linhas: readonly LinhaTriagem[], fila: IdFila): LinhaTriagem[] {
  return linhas.filter(PREDICADOS[fila])
}

export function contarFilas(linhas: readonly LinhaTriagem[]): Record<IdFila, number> {
  return Object.fromEntries(IDS_FILA.map((id) => [id, linhas.filter(PREDICADOS[id]).length])) as Record<IdFila, number>
}

/** Busca por parte do ID, sem diferenciar maiúsculas. */
export function buscarPorId(linhas: readonly LinhaTriagem[], termo: string): LinhaTriagem[] {
  const t = termo.trim().toLowerCase()
  return t ? linhas.filter((l) => l.documentoId.toLowerCase().includes(t)) : [...linhas]
}

// ---------- Meus documentos ----------

export function partesCrm(crm: Crm | string | null): { numero: string; uf: string } | null {
  if (!crm) return null
  if (typeof crm === 'string') {
    const numero = crm.replace(/\D/g, '')
    const uf = (crm.match(/[A-Za-z]{2}\s*$/)?.[0] ?? '').toUpperCase()
    return numero ? { numero, uf } : null
  }
  const numero = (crm.numero ?? '').replace(/\D/g, '')
  return numero ? { numero, uf: (crm.uf ?? '').toUpperCase() } : null
}

/** O CRM extraído do documento é o do médico logado? (UF só conta quando os dois a têm.) */
export function ehDoMedicoLogado(linha: LinhaTriagem): boolean {
  return crmIgual(linha.crmMedico, MEDICO_LOGADO.crm)
}

/** Mesmo CRM? A UF só conta quando os dois lados a têm. */
export function crmIgual(a: Crm | string | null, b: Crm | string | null): boolean {
  const x = partesCrm(a)
  const y = partesCrm(b)
  if (!x || !y) return false
  return x.numero === y.numero && (!x.uf || !y.uf || x.uf === y.uf)
}

// ---------- Células ----------

export const ROTULO_TIPO_CURTO: Record<TipoDocumento, string> = {
  RECEITUARIO_MEDICO: 'Receituário médico',
  LAUDO_EXAME_LABORATORIAL: 'Laudo laboratorial',
  LAUDO_EXAME_IMAGEM: 'Laudo de imagem',
  GUIA_PROCEDIMENTO: 'Guia de procedimento',
  RELATORIO_ALTA_INTERNACAO: 'Relatório de alta',
  ATESTADO_MEDICO: 'Atestado médico',
  OUTRO: 'Outro',
  NAO_IDENTIFICADO: 'Não identificado',
}

export const ROTULO_DESTINO_CURTO: Record<Destino, string> = {
  FILA_URGENCIA_MEDICA: 'Urgência médica',
  FILA_REVISAO_HUMANA: 'Revisão humana',
  PRONTUARIO_ELETRONICO: 'Prontuário eletrônico',
  FARMACIA_HOSPITALAR: 'Farmácia hospitalar',
  AUDITORIA_AUTORIZACOES: 'Auditoria de autorizações',
}

export function rotuloTipoCurto(tipo: string | null): string {
  if (!tipo) return '—'
  return ROTULO_TIPO_CURTO[tipo as TipoDocumento] ?? tipo
}


export function scoreDaLinha(linha: LinhaTriagem): { valor: string; abaixo: string | null } | null {
  if (linha.score === null) return null
  const limiar = linha.limiar ?? 0.85
  return {
    valor: formatarScore(linha.score),
    abaixo: linha.score < limiar ? `abaixo de ${formatarScore(limiar)}` : null,
  }
}

/** HH:mm quando é hoje; "dd/mm HH:mm" nos outros dias. */
export function formatarRecebido(iso: string, agora: Date = new Date()): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  const hora = d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', hour12: false })
  const mesmoDia = d.toDateString() === agora.toDateString()
  if (mesmoDia) return hora
  return `${d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })} ${hora}`
}

export function contadorDocumentos(n: number): string {
  return `· ${n} ${n === 1 ? 'documento' : 'documentos'}`
}

/** Destino do botão "Abrir". */
export function rotaDaLinha(linha: LinhaTriagem): string {
  const id = encodeURIComponent(linha.documentoId)
  return linha.concluida ? `/resultado/${id}` : `/nova-triagem/processamento/${id}`
}
