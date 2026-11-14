/**
 * Dados do envio que a Nova triagem passa para a tela de Processamento (via `location.state`).
 * A API não devolve formato nem canal depois do 202, então só existem quando o usuário chega
 * pelo envio; num acesso direto pela URL o card "Envio" mostra "—".
 */
export type DadosEnvio = {
  /** "Texto" ou a extensão do arquivo em maiúsculas (PDF, JPG...). */
  formato: string
  canal: string
  /** Momento do envio, em ISO 8601. */
  enviadoEm: string
}

export const SEM_DADO = '—'

/** Rótulo do formato: "Texto" para texto colado, senão a extensão do arquivo. */
export function rotuloFormato(arquivo: Pick<File, 'name'> | null): string {
  if (!arquivo) return 'Texto'
  const ponto = arquivo.name.lastIndexOf('.')
  return ponto === -1 ? 'Arquivo' : arquivo.name.slice(ponto + 1).toUpperCase()
}

/** Lê `location.state` com segurança: qualquer coisa fora do formato esperado vira `null`. */
export function lerDadosEnvio(estado: unknown): DadosEnvio | null {
  if (typeof estado !== 'object' || estado === null) return null
  const { formato, canal, enviadoEm } = estado as Record<string, unknown>
  if (typeof formato !== 'string' || typeof canal !== 'string' || typeof enviadoEm !== 'string') return null
  return { formato, canal, enviadoEm }
}

/** "21/10/2026 10:47" no fuso do navegador; `—` quando a data falta ou é inválida. */
export function formatarDataHora(iso: string | null | undefined): string {
  if (!iso) return SEM_DADO
  const data = new Date(iso)
  if (Number.isNaN(data.getTime())) return SEM_DADO
  const dia = data.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' })
  const hora = data.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', hour12: false })
  return `${dia} ${hora}`
}
