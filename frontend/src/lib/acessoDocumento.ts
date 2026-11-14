import type { TriagemMediFlow } from '../types/clinical'
import { crmIgual, partesCrm } from './filasTriagens'
import type { Medico } from './sessao'

export type Acesso = { permitido: true } | { permitido: false; crmDocumento: string }

/**
 * Regra do "Acesso restrito" (Figma 00d), na versão de demonstração:
 * bloqueia quando o documento tem CRM de solicitante extraído, esse CRM não é o da sessão e o
 * documento NÃO foi enviado por este navegador. Quem enviou sempre vê o que enviou.
 */
export function acessoAoDocumento(triagem: TriagemMediFlow, medico: Medico | null, enviadoAqui: boolean): Acesso {
  if (!medico || enviadoAqui) return { permitido: true }
  const crm = triagem.dados_extraidos?.medico.crm ?? null
  const partes = partesCrm(crm)
  if (!partes) return { permitido: true }
  if (crmIgual(crm, medico.crm)) return { permitido: true }
  return { permitido: false, crmDocumento: partes.uf ? `CRM ${partes.numero} / ${partes.uf}` : `CRM ${partes.numero}` }
}
