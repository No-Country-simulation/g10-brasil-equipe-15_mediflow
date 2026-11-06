/**
 * Contrato de dados do MediFlow (espelho de src/schemas/clinical.py, versão 2.0.0).
 * Fonte única da verdade: o backend. Ao alterar o schema Python, atualize este arquivo.
 */

export type TipoDocumento =
  | 'RECEITUARIO_MEDICO'
  | 'LAUDO_EXAME_LABORATORIAL'
  | 'LAUDO_EXAME_IMAGEM'
  | 'GUIA_PROCEDIMENTO'
  | 'RELATORIO_ALTA_INTERNACAO'
  | 'ATESTADO_MEDICO'
  | 'OUTRO'
  | 'NAO_IDENTIFICADO'

export type NivelPrioridade = 'URGENTE' | 'ROTINA' | 'NAO_IDENTIFICADA'

export type StatusTriagem =
  | 'RECEBIDO'
  | 'PROCESSANDO'
  | 'PROCESSADO'
  | 'EM_REVISAO'
  | 'ERRO_PROCESSAMENTO'
  | 'ERRO_PERSISTENCIA'

export type Destino =
  | 'FILA_URGENCIA_MEDICA'
  | 'FARMACIA_HOSPITALAR'
  | 'AUDITORIA_AUTORIZACOES'
  | 'PRONTUARIO_ELETRONICO'
  | 'FILA_REVISAO_HUMANA'

export type Urgencia = 'SIM' | 'NAO' | 'INDETERMINADO'

export type Gravidade = 'ALTA' | 'MEDIA' | 'BAIXA'

export type CodigoErro =
  | 'FORMATO_NAO_SUPORTADO'
  | 'CAMPOS_INVALIDOS'
  | 'REQUISICAO_INVALIDA'
  | 'ARQUIVO_MAIOR_QUE_LIMITE'
  | 'MIME_INVALIDO'
  | 'PDF_PROTEGIDO'
  | 'PDF_CORROMPIDO'
  | 'ERRO_PERSISTENCIA'

export interface Paciente {
  nome?: string | null
  idade?: number | null
  cpf?: string | null
}

export interface Crm {
  numero?: string | null
  uf?: string | null
}

export interface Medico {
  nome?: string | null
  /** O backend aceita CRM estruturado ou texto livre. */
  crm?: Crm | string | null
}

export interface Medicamento {
  nome: string
  dosagem?: string | null
  frequencia?: string | null
}

export interface ItemExameLaboratorial {
  analito: string
  valor_medido: string
  unidade?: string | null
  referencia_impressa?: string | null
  alterado?: boolean | null
}

export interface Conflito {
  tipo: string
  campos: string[]
  gravidade: Gravidade
  descricao: string
}

export interface Classificacao {
  tipo_documento: TipoDocumento | string
  especialidade?: string[] | string | null
  nivel_prioridade: NivelPrioridade
  /** 0 a 1 */
  score_classificacao: number
}

export interface DadosExtraidos {
  paciente: Paciente
  medico: Medico
  diagnostico?: string | null
  cid?: string | null
  exames: string[]
  exames_laboratoriais: ItemExameLaboratorial[]
  medicamentos: Array<Medicamento | string>
  urgencia: Urgencia
  score_confianca_extracao: number
  achados_criticos?: string | null
  inconsistencias_detectadas: string[]
}

export interface Qualidade {
  score_extracao: number
  score_combinado: number
  limiar_aplicado: number
  campos_ausentes: string[]
  campos_incertos: string[]
  conflitos: Conflito[]
}

export interface Notificacao {
  gerada: boolean
  canal: string
  mensagem?: string | null
  status: string
}

export interface DecisaoRoteamento {
  destino_principal?: Destino | null
  destinos: Destino[]
  requer_auditoria_humana: boolean
  justificativa_roteamento: string
  notificacao?: Notificacao | null
}

export interface ArmazenamentoOCI {
  bucket: string
  caminho_objeto?: string | null
  status_backup: string
  modo_simulacao: boolean
}

export interface ErroProcessamento {
  codigo: CodigoErro
  mensagem: string
}

/** Payload final da triagem (GET /api/v1/triagens/{id}). */
export interface TriagemMediFlow {
  status: StatusTriagem
  documento_id: string
  canal_origem?: string | null
  classificacao?: Classificacao | null
  dados_extraidos?: DadosExtraidos | null
  qualidade?: Qualidade | null
  decisao_roteamento?: DecisaoRoteamento | null
  armazenamento_oci?: ArmazenamentoOCI | null
  erro?: ErroProcessamento | null
  versao_esquema: string
}
