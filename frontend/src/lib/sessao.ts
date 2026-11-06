/**
 * Login de DEMONSTRAÇÃO, só no front (decisão do time em 2026-11-04). Não há autenticação no
 * backend: se CRM, UF e senha forem os da conta abaixo, entra; senão, não entra. Nada aqui é
 * segurança; é só o estado de "logado" da demonstração.
 */
import { MEDICO_LOGADO } from './medicoLogado'

export const CONTA_DEMO = {
  crm: MEDICO_LOGADO.crm.numero,
  uf: MEDICO_LOGADO.crm.uf,
  senha: 'mediflow',
  medico: MEDICO_LOGADO,
} as const

export type Medico = { nome: string; crm: { numero: string; uf: string } }

export type Sessao = {
  medico: Medico
  /** ms desde a época */
  iniciadaEm: number
  ultimaAtividade: number
  /** "Manter conectado": guarda no localStorage e não expira por inatividade. */
  manter: boolean
}

export const INATIVIDADE_MAX_MS = 30 * 60 * 1000
export const MAX_TENTATIVAS = 5
export const BLOQUEIO_MS = 15 * 60 * 1000

const CHAVE_SESSAO = 'mediflow:sessao'
const CHAVE_TENTATIVAS = 'mediflow:login-tentativas'

// ---------- storage seguro ----------

type Armazem = 'local' | 'sessao'

function storage(qual: Armazem): Storage | null {
  try {
    return qual === 'local' ? localStorage : sessionStorage
  } catch {
    return null
  }
}

function ler<T>(qual: Armazem, chave: string): T | null {
  try {
    const bruto = storage(qual)?.getItem(chave)
    return bruto ? (JSON.parse(bruto) as T) : null
  } catch {
    return null
  }
}

function gravar(qual: Armazem, chave: string, valor: unknown) {
  try {
    storage(qual)?.setItem(chave, JSON.stringify(valor))
  } catch {
    // Sem storage: a sessão vale só até recarregar a página.
  }
}

function remover(qual: Armazem, chave: string) {
  try {
    storage(qual)?.removeItem(chave)
  } catch {
    // ignora
  }
}

// ---------- credenciais ----------

export type Credenciais = { crm: string; uf: string; senha: string }

export function credenciaisValidas({ crm, uf, senha }: Credenciais): boolean {
  return crm.replace(/\D/g, '') === CONTA_DEMO.crm && uf.trim().toUpperCase() === CONTA_DEMO.uf && senha.trim() === CONTA_DEMO.senha
}

// ---------- sessão ----------

function valida(s: unknown): s is Sessao {
  if (typeof s !== 'object' || s === null) return false
  const v = s as Record<string, unknown>
  return typeof v.iniciadaEm === 'number' && typeof v.ultimaAtividade === 'number' && typeof v.medico === 'object' && v.medico !== null
}

export function iniciarSessao(manter: boolean, agora = Date.now()): Sessao {
  const sessao: Sessao = {
    medico: { nome: CONTA_DEMO.medico.nome, crm: { ...CONTA_DEMO.medico.crm } },
    iniciadaEm: agora,
    ultimaAtividade: agora,
    manter,
  }
  remover(manter ? 'sessao' : 'local', CHAVE_SESSAO)
  gravar(manter ? 'local' : 'sessao', CHAVE_SESSAO, sessao)
  return sessao
}

export type LeituraSessao = { tipo: 'ativa'; sessao: Sessao } | { tipo: 'expirada' } | { tipo: 'nenhuma' }

/** Lê a sessão; uma sessão vencida por inatividade é apagada e devolvida como "expirada". */
export function lerSessao(agora = Date.now()): LeituraSessao {
  const sessao = [ler<Sessao>('sessao', CHAVE_SESSAO), ler<Sessao>('local', CHAVE_SESSAO)].find(valida)
  if (!sessao) return { tipo: 'nenhuma' }
  if (!sessao.manter && agora - sessao.ultimaAtividade > INATIVIDADE_MAX_MS) {
    encerrarSessao()
    return { tipo: 'expirada' }
  }
  return { tipo: 'ativa', sessao }
}

/** Marca atividade (navegação entre telas), adiando a expiração. */
export function tocarSessao(agora = Date.now()) {
  const leitura = lerSessao(agora)
  if (leitura.tipo !== 'ativa') return
  const { sessao } = leitura
  gravar(sessao.manter ? 'local' : 'sessao', CHAVE_SESSAO, { ...sessao, ultimaAtividade: agora })
}

export function encerrarSessao() {
  remover('sessao', CHAVE_SESSAO)
  remover('local', CHAVE_SESSAO)
}

// ---------- tentativas e bloqueio ----------

type Tentativas = { falhas: number; bloqueadoAte: number | null }

function lerTentativas(agora: number): Tentativas {
  const t = ler<Tentativas>('local', CHAVE_TENTATIVAS) ?? { falhas: 0, bloqueadoAte: null }
  // Bloqueio vencido: recomeça a contagem.
  if (t.bloqueadoAte !== null && agora >= t.bloqueadoAte) return { falhas: 0, bloqueadoAte: null }
  return t
}

/** Momento (ms) até quando o login está bloqueado, ou `null`. */
export function bloqueadoAte(agora = Date.now()): number | null {
  return lerTentativas(agora).bloqueadoAte
}

/** Conta uma falha; na 5ª, bloqueia por 15 minutos. */
export function registrarFalha(agora = Date.now()): Tentativas {
  const atual = lerTentativas(agora)
  const falhas = atual.falhas + 1
  const novo: Tentativas = { falhas, bloqueadoAte: falhas >= MAX_TENTATIVAS ? agora + BLOQUEIO_MS : null }
  gravar('local', CHAVE_TENTATIVAS, novo)
  return novo
}

export function limparTentativas() {
  remover('local', CHAVE_TENTATIVAS)
}
