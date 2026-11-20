/**
 * Registro local dos envios aceitos (202) por este navegador. É a base provisória da lista de
 * triagens enquanto a API não tem `GET /api/v1/triagens`. Falha de storage nunca quebra a tela.
 */

export type EnvioRegistrado = {
  documentoId: string
  canal: string | null
  /** ISO 8601 */
  enviadoEm: string
}

export const CHAVE_REGISTRO = 'mediflow:triagens-enviadas'
export const MAX_REGISTROS = 50

function valido(item: unknown): item is EnvioRegistrado {
  if (typeof item !== 'object' || item === null) return false
  const { documentoId, canal, enviadoEm } = item as Record<string, unknown>
  return typeof documentoId === 'string' && typeof enviadoEm === 'string' && (canal === null || typeof canal === 'string')
}

/** Mais recente primeiro. */
export function lerRegistro(): EnvioRegistrado[] {
  try {
    const bruto: unknown = JSON.parse(localStorage.getItem(CHAVE_REGISTRO) ?? '[]')
    return Array.isArray(bruto) ? bruto.filter(valido) : []
  } catch {
    return []
  }
}

function gravar(lista: EnvioRegistrado[]) {
  try {
    localStorage.setItem(CHAVE_REGISTRO, JSON.stringify(lista.slice(0, MAX_REGISTROS)))
  } catch {
    // Sem localStorage (modo privado, cota cheia): a lista fica só com o que já havia.
  }
}

/** Registra um envio; reenviar o mesmo ID só o move para o topo. */
export function registrarEnvio(envio: EnvioRegistrado) {
  gravar([envio, ...lerRegistro().filter((e) => e.documentoId !== envio.documentoId)])
}

/** Remove IDs que a API não conhece mais (ex.: backend reiniciado, já que guarda tudo em memória). */
export function esquecerEnvios(ids: readonly string[]) {
  if (ids.length === 0) return
  const remover = new Set(ids)
  gravar(lerRegistro().filter((e) => !remover.has(e.documentoId)))
}
