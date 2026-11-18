import { createContext, useContext } from 'react'
import type { Credenciais, Sessao } from '../lib/sessao'

export type MotivoSaida = 'expirada' | null

export type ResultadoLogin =
  | { ok: true }
  | { ok: false; erro: 'invalidas'; restantes: number }
  | { ok: false; erro: 'bloqueado'; ate: number }

export type ContextoSessao = {
  sessao: Sessao | null
  /** Por que a última sessão terminou (para o aviso da 00c). */
  motivo: MotivoSaida
  entrar: (credenciais: Credenciais, manter: boolean) => ResultadoLogin
  sair: (motivo?: MotivoSaida) => void
}

/** Estado de navegação passado ao login: para onde voltar e por que saiu. */
export type EstadoLogin = { de?: string; motivo?: MotivoSaida }

export const Contexto = createContext<ContextoSessao | null>(null)

export function useSessao(): ContextoSessao {
  const contexto = useContext(Contexto)
  if (!contexto) throw new Error('useSessao precisa estar dentro de <SessaoProvider>.')
  return contexto
}
