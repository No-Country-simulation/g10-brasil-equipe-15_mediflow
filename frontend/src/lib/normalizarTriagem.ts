import type {
  Classificacao,
  Conflito,
  DadosExtraidos,
  DecisaoRoteamento,
  Destino,
  Medico,
  NivelPrioridade,
  Notificacao,
  Qualidade,
  StatusTriagem,
  TriagemMediFlow,
  Urgencia,
} from '../types/clinical'

/**
 * Converte um JSON de triagem para o tipo `TriagemMediFlow` (contrato atual).
 *
 * Aceita dois formatos:
 * - o contrato atual (`expected.json` dos fixtures), que só ganha os campos que o tipo exige;
 * - o formato anterior dos `cenario_*.json` (`medico_solicitante`, `diagnostico_principal`,
 *   `Prontuario_Eletronico_Paciente`, `Rotina`...), que é traduzido campo a campo.
 *
 * Valores desconhecidos de status, prioridade e destino lançam erro, em vez de passarem em silêncio.
 */

type Obj = Record<string, unknown>

const STATUS: readonly StatusTriagem[] = [
  'RECEBIDO',
  'PROCESSANDO',
  'PROCESSADO',
  'EM_REVISAO',
  'ERRO_PROCESSAMENTO',
  'ERRO_PERSISTENCIA',
]

/** Chaves já sem acento, em maiúsculas. Os apelidos espelham os aliases de `clinical.py`. */
const DESTINOS: Record<string, Destino> = {
  FILA_URGENCIA_MEDICA: 'FILA_URGENCIA_MEDICA',
  FARMACIA_HOSPITALAR: 'FARMACIA_HOSPITALAR',
  AUDITORIA_AUTORIZACOES: 'AUDITORIA_AUTORIZACOES',
  PRONTUARIO_ELETRONICO: 'PRONTUARIO_ELETRONICO',
  FILA_REVISAO_HUMANA: 'FILA_REVISAO_HUMANA',
  EMERGENCIA: 'FILA_URGENCIA_MEDICA',
  EMERGENCIA_MEDICA: 'FILA_URGENCIA_MEDICA',
  FILA_EMERGENCIA: 'FILA_URGENCIA_MEDICA',
  FILA_EMERGENCIA_MEDICA: 'FILA_URGENCIA_MEDICA',
  AUDITORIA: 'AUDITORIA_AUTORIZACOES',
  FARMACIA: 'FARMACIA_HOSPITALAR',
  PRONTUARIO: 'PRONTUARIO_ELETRONICO',
  PRONTUARIO_ELETRONICO_PACIENTE: 'PRONTUARIO_ELETRONICO',
  REVISAO_HUMANA: 'FILA_REVISAO_HUMANA',
}

const PRIORIDADES: Record<string, NivelPrioridade> = {
  URGENTE: 'URGENTE',
  ROTINA: 'ROTINA',
  POUCO_URGENTE: 'ROTINA',
  NAO_IDENTIFICADA: 'NAO_IDENTIFICADA',
  AMBIGUO: 'NAO_IDENTIFICADA',
}

function chave(valor: string): string {
  return valor
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .trim()
    .toUpperCase()
    .replace(/[\s-]+/g, '_')
}

function obj(valor: unknown, onde: string): Obj {
  if (valor === null || typeof valor !== 'object' || Array.isArray(valor)) {
    throw new Error(`Triagem inválida: "${onde}" deveria ser um objeto.`)
  }
  return valor as Obj
}

function objOuNulo(valor: unknown): Obj | null {
  return valor !== null && typeof valor === 'object' && !Array.isArray(valor)
    ? (valor as Obj)
    : null
}

function texto(valor: unknown): string | null {
  return typeof valor === 'string' && valor !== '' ? valor : null
}

function numero(valor: unknown, padrao: number): number {
  return typeof valor === 'number' ? valor : padrao
}

function lista<T>(valor: unknown): T[] {
  return Array.isArray(valor) ? (valor as T[]) : []
}

function primeiro<T>(...valores: Array<T | null | undefined>): T | undefined {
  return valores.find((v) => v !== null && v !== undefined)
}

function mapear<T>(tabela: Record<string, T>, valor: unknown, rotulo: string): T {
  const encontrado = typeof valor === 'string' ? tabela[chave(valor)] : undefined
  if (encontrado === undefined) {
    throw new Error(`Triagem inválida: ${rotulo} desconhecido (${JSON.stringify(valor)}).`)
  }
  return encontrado
}

function normalizarClassificacao(bruto: Obj): Classificacao {
  return {
    tipo_documento: texto(bruto.tipo_documento) ?? 'NAO_IDENTIFICADO',
    especialidade: (bruto.especialidade as Classificacao['especialidade']) ?? null,
    nivel_prioridade: mapear(PRIORIDADES, bruto.nivel_prioridade, 'nivel_prioridade'),
    score_classificacao: numero(
      primeiro(
        bruto.score_classificacao as number | undefined,
        bruto.score_confianca_classificacao as number | undefined,
      ),
      0,
    ),
  }
}

function normalizarMedico(bruto: Obj): Medico {
  const medico = objOuNulo(bruto.medico) ?? objOuNulo(bruto.medico_solicitante)
  if (!medico) return {}
  // No formato anterior, `crm_detalhado` (estruturado) tem prioridade sobre `crm` (texto livre).
  const crm = primeiro(
    objOuNulo(medico.crm_detalhado) as Medico['crm'] | null,
    medico.crm as Medico['crm'] | undefined,
  )
  return { nome: texto(medico.nome), crm: crm ?? null }
}

function urgenciaDe(bruto: Obj, prioridade: NivelPrioridade | undefined): Urgencia {
  const informada = texto(bruto.urgencia)
  if (informada) return informada as Urgencia
  // Formato anterior não tem o campo: deduz da prioridade da classificação.
  if (prioridade === 'URGENTE') return 'SIM'
  if (prioridade === 'ROTINA') return 'NAO'
  return 'INDETERMINADO'
}

function normalizarDados(
  bruto: Obj,
  qualidade: Qualidade | null,
  prioridade: NivelPrioridade | undefined,
): DadosExtraidos {
  const exameUnico = texto(bruto.exame_ou_procedimento)
  const exames = lista<string>(bruto.exames)
  return {
    paciente: objOuNulo(bruto.paciente) ?? {},
    medico: normalizarMedico(bruto),
    diagnostico: primeiro(texto(bruto.diagnostico), texto(bruto.diagnostico_principal)) ?? null,
    cid: primeiro(texto(bruto.cid), texto(bruto.cid_extraido)) ?? null,
    exames: exames.length > 0 ? exames : exameUnico ? [exameUnico] : [],
    exames_laboratoriais: lista(bruto.exames_laboratoriais),
    medicamentos: lista(bruto.medicamentos),
    urgencia: urgenciaDe(bruto, prioridade),
    score_confianca_extracao: numero(
      bruto.score_confianca_extracao,
      qualidade?.score_extracao ?? 0,
    ),
    achados_criticos: texto(bruto.achados_criticos),
    inconsistencias_detectadas: lista(bruto.inconsistencias_detectadas),
  }
}

function normalizarQualidade(bruto: Obj): Qualidade {
  return {
    score_extracao: numero(bruto.score_extracao, 0),
    score_combinado: numero(bruto.score_combinado, 0),
    limiar_aplicado: numero(bruto.limiar_aplicado, 0.85),
    campos_ausentes: lista(bruto.campos_ausentes),
    campos_incertos: lista(primeiro(bruto.campos_incertos, bruto.campos_incerto)),
    conflitos: lista<Conflito>(bruto.conflitos),
  }
}

function normalizarNotificacao(bruto: unknown): Notificacao | null {
  const n = objOuNulo(bruto)
  if (!n) return null
  return {
    gerada: n.gerada === true,
    canal: texto(n.canal) ?? 'SIMULADO_SLACK_PLANTAO',
    mensagem: texto(n.mensagem),
    status: texto(n.status) ?? 'REGISTRADA',
  }
}

function normalizarRoteamento(bruto: Obj): DecisaoRoteamento {
  const principal = bruto.destino_principal
  return {
    destino_principal: principal ? mapear(DESTINOS, principal, 'destino_principal') : null,
    destinos: lista<string>(bruto.destinos).map((d) => mapear(DESTINOS, d, 'destino')),
    requer_auditoria_humana: bruto.requer_auditoria_humana === true,
    justificativa_roteamento: texto(bruto.justificativa_roteamento) ?? '',
    notificacao: normalizarNotificacao(primeiro(bruto.notificacao, bruto.notificacao_gerada)),
  }
}

export function normalizarTriagem(entrada: unknown): TriagemMediFlow {
  const bruto = obj(entrada, 'raiz')

  const status = bruto.status as StatusTriagem
  if (!STATUS.includes(status)) {
    throw new Error(`Triagem inválida: status desconhecido (${JSON.stringify(bruto.status)}).`)
  }

  const brutoClassificacao = objOuNulo(bruto.classificacao)
  const classificacao = brutoClassificacao ? normalizarClassificacao(brutoClassificacao) : null

  const brutoQualidade = objOuNulo(bruto.qualidade)
  const qualidade = brutoQualidade ? normalizarQualidade(brutoQualidade) : null

  const brutoDados = objOuNulo(bruto.dados_extraidos)
  const brutoRoteamento = objOuNulo(bruto.decisao_roteamento)
  const brutoOci = objOuNulo(bruto.armazenamento_oci)
  const brutoErro = objOuNulo(bruto.erro)

  return {
    status,
    documento_id: texto(bruto.documento_id) ?? '',
    canal_origem: texto(bruto.canal_origem),
    classificacao,
    dados_extraidos: brutoDados
      ? normalizarDados(brutoDados, qualidade, classificacao?.nivel_prioridade)
      : null,
    qualidade,
    decisao_roteamento: brutoRoteamento ? normalizarRoteamento(brutoRoteamento) : null,
    armazenamento_oci: brutoOci
      ? {
          bucket: texto(brutoOci.bucket) ?? '',
          caminho_objeto: texto(brutoOci.caminho_objeto),
          status_backup: texto(brutoOci.status_backup) ?? '',
          // Ausente no formato anterior; os fixtures são todos simulados.
          modo_simulacao: brutoOci.modo_simulacao !== false,
        }
      : null,
    erro: brutoErro ? (brutoErro as unknown as TriagemMediFlow['erro']) : null,
    versao_esquema: texto(bruto.versao_esquema) ?? 'desconhecida',
  }
}
