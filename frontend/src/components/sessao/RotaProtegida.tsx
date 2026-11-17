import { useEffect } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router'
import { useSessao } from '../../hooks/useSessao'
import type { EstadoLogin } from '../../hooks/useSessao'
import { lerSessao, tocarSessao } from '../../lib/sessao'

/** Exige sessão; a cada troca de tela confere a inatividade e marca atividade. */
export function RotaProtegida() {
  const { sessao, motivo, sair } = useSessao()
  const local = useLocation()

  useEffect(() => {
    if (!sessao) return
    const leitura = lerSessao()
    if (leitura.tipo === 'ativa') tocarSessao()
    else sair(leitura.tipo === 'expirada' ? 'expirada' : null)
  }, [local.pathname, sessao, sair])

  if (!sessao) {
    const estado: EstadoLogin = { de: local.pathname + local.search, motivo }
    return <Navigate to="/login" replace state={estado} />
  }
  return <Outlet />
}
