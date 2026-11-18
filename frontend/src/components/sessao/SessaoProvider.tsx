import { useCallback, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { Contexto } from '../../hooks/useSessao'
import type { MotivoSaida, ResultadoLogin } from '../../hooks/useSessao'
import {
  bloqueadoAte,
  credenciaisValidas,
  encerrarSessao,
  iniciarSessao,
  limparTentativas,
  lerSessao,
  MAX_TENTATIVAS,
  registrarFalha,
} from '../../lib/sessao'
import type { Credenciais, Sessao } from '../../lib/sessao'

/** Guarda a sessão de demonstração e expõe entrar/sair (login fake, só no front). */
export function SessaoProvider({ children }: { children: ReactNode }) {
  const [estado, setEstado] = useState<{ sessao: Sessao | null; motivo: MotivoSaida }>(() => {
    const leitura = lerSessao()
    return { sessao: leitura.tipo === 'ativa' ? leitura.sessao : null, motivo: leitura.tipo === 'expirada' ? 'expirada' : null }
  })

  const entrar = useCallback((credenciais: Credenciais, manter: boolean): ResultadoLogin => {
    const ate = bloqueadoAte()
    if (ate !== null) return { ok: false, erro: 'bloqueado', ate }
    if (!credenciaisValidas(credenciais)) {
      const t = registrarFalha()
      if (t.bloqueadoAte !== null) return { ok: false, erro: 'bloqueado', ate: t.bloqueadoAte }
      return { ok: false, erro: 'invalidas', restantes: MAX_TENTATIVAS - t.falhas }
    }
    limparTentativas()
    setEstado({ sessao: iniciarSessao(manter), motivo: null })
    return { ok: true }
  }, [])

  const sair = useCallback((motivo: MotivoSaida = null) => {
    encerrarSessao()
    setEstado({ sessao: null, motivo })
  }, [])

  const valor = useMemo(() => ({ ...estado, entrar, sair }), [estado, entrar, sair])
  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>
}
