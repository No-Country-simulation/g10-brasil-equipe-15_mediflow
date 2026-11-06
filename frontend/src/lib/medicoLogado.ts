/**
 * Médica "logada" de demonstração. A API ainda não tem autenticação (Fase 5); até lá este mock
 * alimenta o card da sidebar e o filtro de "Meus documentos".
 */
export const MEDICO_LOGADO = {
  nome: 'Dra. Renata Silveira',
  crm: { numero: '145892', uf: 'SP' },
} as const

export const CRM_LOGADO_TEXTO = `CRM ${MEDICO_LOGADO.crm.numero} / ${MEDICO_LOGADO.crm.uf}`

export function iniciais(nome: string): string {
  const partes = nome.split(' ').filter((p) => p && !/^(dr|dra)\.?$/i.test(p))
  return ((partes[0]?.[0] ?? '') + (partes.length > 1 ? (partes[partes.length - 1]?.[0] ?? '') : '')).toUpperCase()
}
