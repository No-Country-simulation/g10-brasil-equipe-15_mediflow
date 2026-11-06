import type { BadgeTone } from '../components/ui/Badge'
import type { Destino, NivelPrioridade, TipoDocumento, Urgencia } from '../types/clinical'

/** Rótulos legíveis dos enums do contrato, usados nas telas. */

export const ROTULO_TIPO_DOCUMENTO: Record<TipoDocumento, string> = {
  RECEITUARIO_MEDICO: 'Receituário médico',
  LAUDO_EXAME_LABORATORIAL: 'Laudo de exame laboratorial',
  LAUDO_EXAME_IMAGEM: 'Laudo de exame de imagem',
  GUIA_PROCEDIMENTO: 'Guia de procedimento',
  RELATORIO_ALTA_INTERNACAO: 'Relatório de alta de internação',
  ATESTADO_MEDICO: 'Atestado médico',
  OUTRO: 'Outro',
  NAO_IDENTIFICADO: 'Não identificado',
}

export function rotuloTipoDocumento(tipo: string): string {
  return ROTULO_TIPO_DOCUMENTO[tipo as TipoDocumento] ?? tipo
}

export const ROTULO_DESTINO: Record<Destino, string> = {
  FILA_URGENCIA_MEDICA: 'Fila de urgência médica',
  FARMACIA_HOSPITALAR: 'Farmácia hospitalar',
  AUDITORIA_AUTORIZACOES: 'Auditoria de autorizações',
  PRONTUARIO_ELETRONICO: 'Prontuário eletrônico',
  FILA_REVISAO_HUMANA: 'Fila de revisão humana',
}

export const PRIORIDADE: Record<NivelPrioridade, { rotulo: string; tom: BadgeTone }> = {
  URGENTE: { rotulo: 'Urgente', tom: 'danger' },
  ROTINA: { rotulo: 'Rotina', tom: 'neutral' },
  NAO_IDENTIFICADA: { rotulo: 'Não identificada', tom: 'neutral' },
}

export const URGENCIA: Record<Urgencia, { rotulo: string; tom: BadgeTone }> = {
  SIM: { rotulo: 'Sim — urgência detectada', tom: 'danger' },
  NAO: { rotulo: 'Não', tom: 'neutral' },
  INDETERMINADO: { rotulo: 'Indeterminado', tom: 'warning' },
}

/** Rótulo dos campos de `dados_extraidos`, pelo caminho usado em `campos_ausentes`/`campos_incertos`. */
export const ROTULO_CAMPO: Record<string, string> = {
  'paciente.nome': 'Paciente',
  'paciente.idade': 'Idade',
  'medico.nome': 'Médico solicitante',
  'medico.crm': 'CRM',
  diagnostico: 'Diagnóstico / hipótese',
  cid: 'CID-10',
}

/** Campos obrigatórios do contrato (os mesmos de tests/test_contrato_fixtures.py). */
export const CAMPOS_OBRIGATORIOS: ReadonlySet<string> = new Set([
  'paciente.nome',
  'paciente.idade',
  'medico.nome',
  'medico.crm',
  'diagnostico',
])

export const ROTULO_GRAVIDADE = { ALTA: 'Gravidade alta', MEDIA: 'Gravidade média', BAIXA: 'Gravidade baixa' } as const
