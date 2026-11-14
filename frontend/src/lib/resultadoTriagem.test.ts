import { describe, expect, it } from 'vitest'
import { CENARIOS_DEMO, RESPOSTAS_ESPERADAS } from '../fixtures'
import conflitoDose from '../fixtures/expected/conflito_dose.json'
import urgenteRevisao from '../fixtures/expected/urgente_revisao.json'
import type { EventoHistorico } from '../types/api'
import type { TriagemMediFlow } from '../types/clinical'
import { normalizarTriagem } from './normalizarTriagem'
import {
  alertaDeErro,
  bannersDe,
  confiancaDe,
  conflitosDoMedicamento,
  formatarCrm,
  formatarEspecialidade,
  formatarIdade,
  MOTIVO_REVISAO_GENERICO,
  motivosDaRevisao,
  ordenarHistorico,
  rotuloSinalizacao,
  situacaoDoAlerta,
  situacaoDoCampo,
  textoFalhaAlerta,
  tomDoStatus,
} from './resultadoTriagem'

const comDose = normalizarTriagem(conflitoDose.resposta_esperada)
const simultaneo = normalizarTriagem(urgenteRevisao.resposta_esperada)

describe('bannersDe', () => {
  it('03a rotina: só o banner de sucesso, com a justificativa', () => {
    const banners = bannersDe(RESPOSTAS_ESPERADAS.rotina)
    expect(banners.map((b) => b.tipo)).toEqual(['sucesso'])
    expect(banners[0]).toMatchObject({ titulo: 'Processado · encaminhado automaticamente' })
  })

  it('03b urgente: banner urgente com a nota do alerta simulado', () => {
    const [banner] = bannersDe(CENARIOS_DEMO.urgente)
    expect(banner).toMatchObject({
      tipo: 'urgente',
      titulo: 'Urgente · encaminhado à fila de urgência médica',
      nota: 'Alerta registrado como evento simulado (SIMULADO_SLACK_PLANTAO). Nenhuma mensagem foi enviada a serviço externo.',
    })
  })

  it('03c urgente + revisão: os dois banners, urgente primeiro', () => {
    expect(bannersDe(simultaneo).map((b) => b.tipo)).toEqual(['urgente', 'revisao'])
  })

  it('03d ambíguo: banner de revisão com os motivos', () => {
    const banners = bannersDe(CENARIOS_DEMO.ambiguo)
    expect(banners.map((b) => b.tipo)).toEqual(['revisao'])
    const revisao = banners[0]
    if (revisao.tipo !== 'revisao') throw new Error('esperava revisão')
    expect(revisao.itens).toEqual([
      'Médico solicitante não consta no documento',
      'CRM não consta no documento',
      'Score combinado 0,65 abaixo do limiar 0,85',
    ])
    expect(revisao.nota).toMatch(/fila é lógica/)
  })

  it('erros não mostram banners (a página usa o alerta de erro)', () => {
    const erro: TriagemMediFlow = { ...RESPOSTAS_ESPERADAS.rotina, status: 'ERRO_PERSISTENCIA' }
    expect(bannersDe(erro)).toEqual([])
  })
})

describe('motivosDaRevisao', () => {
  it('inclui conflitos médios ou altos e ignora os de gravidade baixa', () => {
    expect(motivosDaRevisao(comDose)).toContain('Conflito de gravidade alta: Losartana 500 mg excede a dose usual (50–100 mg)')
    const baixa: TriagemMediFlow = {
      ...comDose,
      qualidade: { ...comDose.qualidade!, conflitos: [{ ...comDose.qualidade!.conflitos[0], gravidade: 'BAIXA' }] },
    }
    expect(motivosDaRevisao(baixa).some((m) => m.startsWith('Conflito'))).toBe(false)
  })

  it('cita campos incertos', () => {
    const incerto: TriagemMediFlow = {
      ...RESPOSTAS_ESPERADAS.rotina,
      qualidade: { ...RESPOSTAS_ESPERADAS.rotina.qualidade!, campos_incertos: ['medico.crm'] },
    }
    expect(motivosDaRevisao(incerto)).toContain('CRM incerto ou ilegível')
  })

  const comTipo = (tipo: string) =>
    ({
      ...RESPOSTAS_ESPERADAS.rotina,
      classificacao: { ...RESPOSTAS_ESPERADAS.rotina.classificacao!, tipo_documento: tipo },
    }) as TriagemMediFlow

  it.each([
    ['OUTRO', 'Outro'],
    ['NAO_IDENTIFICADO', 'Não identificado'],
  ])('tipo de documento %s fica fora da taxonomia', (tipo, rotulo) => {
    expect(motivosDaRevisao(comTipo(tipo))).toContain(`Tipo de documento fora da taxonomia (${rotulo})`)
  })

  it('apelido de tipo aceito pelo backend não vira "fora da taxonomia"', () => {
    expect(motivosDaRevisao(comTipo('LAUDO_LABORATORIAL')).some((m) => m.startsWith('Tipo de documento'))).toBe(false)
  })

  it('prioridade não identificada gera motivo, mesmo sem qualidade, sem duplicar a urgência deduzida', () => {
    const base = RESPOSTAS_ESPERADAS.rotina
    const t: TriagemMediFlow = {
      ...base,
      qualidade: null,
      classificacao: { ...base.classificacao!, nivel_prioridade: 'NAO_IDENTIFICADA' },
      dados_extraidos: { ...base.dados_extraidos!, urgencia: 'INDETERMINADO' },
    }
    expect(motivosDaRevisao(t)).toEqual(['Prioridade não identificada'])
  })

  it('urgência indeterminada com prioridade definida gera motivo', () => {
    const base = RESPOSTAS_ESPERADAS.rotina
    const t: TriagemMediFlow = { ...base, dados_extraidos: { ...base.dados_extraidos!, urgencia: 'INDETERMINADO' } }
    expect(motivosDaRevisao(t)).toContain('Urgência clínica indeterminada')
  })

  it('sem nenhum motivo reconhecido, usa a justificativa do roteamento', () => {
    const t = RESPOSTAS_ESPERADAS.rotina
    expect(motivosDaRevisao(t)).toEqual([t.decisao_roteamento!.justificativa_roteamento])
  })

  it('sem motivo nem justificativa, usa o texto genérico', () => {
    const base = RESPOSTAS_ESPERADAS.rotina
    const t: TriagemMediFlow = { ...base, decisao_roteamento: { ...base.decisao_roteamento!, justificativa_roteamento: '' } }
    expect(motivosDaRevisao(t)).toEqual([MOTIVO_REVISAO_GENERICO])
  })

  it('a justificativa não entra quando já há motivos', () => {
    expect(motivosDaRevisao(CENARIOS_DEMO.ambiguo)).not.toContain(
      CENARIOS_DEMO.ambiguo.decisao_roteamento!.justificativa_roteamento,
    )
  })
})

describe('situacaoDoAlerta', () => {
  const urgente = CENARIOS_DEMO.urgente
  const comNotificacao = (t: TriagemMediFlow, n: { gerada: boolean; status: string } | null): TriagemMediFlow => ({
    ...t,
    decisao_roteamento: {
      ...t.decisao_roteamento!,
      notificacao: n && { canal: 'SIMULADO_SLACK_PLANTAO', ...n },
    },
  })

  it('gerada com status normal está registrada', () => {
    expect(situacaoDoAlerta(urgente)).toEqual({ tipo: 'registrado', canal: 'SIMULADO_SLACK_PLANTAO' })
  })

  it('urgente sem notificação falhou, sem status no texto', () => {
    const t = comNotificacao(urgente, null)
    expect(situacaoDoAlerta(t)).toEqual({ tipo: 'falhou', status: null })
    expect(textoFalhaAlerta(null)).not.toContain('status')
  })

  it.each(['FALHA_REGISTRO', 'erro_oci'])('status %s falha mesmo com gerada=true', (status) => {
    const t = comNotificacao(urgente, { gerada: true, status })
    expect(situacaoDoAlerta(t)).toEqual({ tipo: 'falhou', status })
    expect(textoFalhaAlerta(status)).toContain(`(status ${status})`)
  })

  it('urgente com gerada=false e status padrão falhou, sem status no texto', () => {
    const t = comNotificacao(urgente, { gerada: false, status: 'REGISTRADA' })
    expect(situacaoDoAlerta(t)).toEqual({ tipo: 'falhou', status: null })
  })

  it('status que só contém "erro" no meio não é falha', () => {
    const t = comNotificacao(urgente, { gerada: true, status: 'SEM_ERRO' })
    expect(situacaoDoAlerta(t).tipo).toBe('registrado')
  })

  it('não urgente com status de falha não mostra falha de alerta', () => {
    const t = comNotificacao(RESPOSTAS_ESPERADAS.rotina, { gerada: false, status: 'FALHA' })
    expect(situacaoDoAlerta(t)).toEqual({ tipo: 'nenhum' })
  })

  it('não urgente sem notificação não tem alerta', () => {
    expect(situacaoDoAlerta(RESPOSTAS_ESPERADAS.rotina)).toEqual({ tipo: 'nenhum' })
  })

  it('banner urgente usa o texto de falha na nota', () => {
    const [banner] = bannersDe(comNotificacao(urgente, null))
    expect(banner).toMatchObject({ tipo: 'urgente', nota: textoFalhaAlerta(null) })
  })
})

describe('ordenarHistorico', () => {
  const evento = (id: string, criado_em: string): EventoHistorico => ({
    evento_id: id,
    documento_id: 'DOC-1',
    tipo_evento: 'X',
    criado_em,
    ator: 'API',
    status_novo: 'PROCESSADO',
    versao_esquema: '2.0.0',
  })
  const ids = (es: EventoHistorico[]) => es.map((e) => e.evento_id)

  it('ordena por criado_em crescente sem alterar o array original', () => {
    const entrada = [evento('b', '2026-10-21T13:49:10Z'), evento('a', '2026-10-21T13:49:02Z')]
    expect(ids(ordenarHistorico(entrada))).toEqual(['a', 'b'])
    expect(ids(entrada)).toEqual(['b', 'a'])
  })

  it('mantém a ordem de chegada em empates', () => {
    const t = '2026-10-21T13:49:02Z'
    expect(ids(ordenarHistorico([evento('1', t), evento('2', t), evento('0', '2026-10-21T13:00:00Z')]))).toEqual(['0', '1', '2'])
  })

  it('datas inválidas vão para o fim, na ordem original', () => {
    const entrada = [evento('x', 'lixo'), evento('b', '2026-10-21T13:49:10Z'), evento('y', ''), evento('a', '2026-10-21T13:49:02Z')]
    expect(ids(ordenarHistorico(entrada))).toEqual(['a', 'b', 'x', 'y'])
  })
})

describe('situacaoDoCampo', () => {
  const t = CENARIOS_DEMO.ambiguo

  it('ausente obrigatório exige revisão; ausente opcional não', () => {
    expect(situacaoDoCampo(t, 'medico.crm', null)).toEqual({ tipo: 'ausente', exigeRevisao: true })
    expect(situacaoDoCampo(t, 'cid', null)).toEqual({ tipo: 'ausente', exigeRevisao: false })
  })

  it('valor vazio conta como ausente mesmo fora de campos_ausentes', () => {
    expect(situacaoDoCampo(RESPOSTAS_ESPERADAS.rotina, 'paciente.idade', null)).toMatchObject({ tipo: 'ausente' })
  })

  it('incerto tem prioridade e presente é o resto', () => {
    const incerto: TriagemMediFlow = { ...t, qualidade: { ...t.qualidade!, campos_incertos: ['paciente.nome'] } }
    expect(situacaoDoCampo(incerto, 'paciente.nome', 'Maria')).toEqual({ tipo: 'incerto' })
    expect(situacaoDoCampo(t, 'paciente.nome', 'Maria')).toEqual({ tipo: 'presente' })
  })
})

describe('confiancaDe', () => {
  it('rotina: acima do limiar e com a fórmula do mínimo', () => {
    const c = confiancaDe(CENARIOS_DEMO.rotina)!
    expect(c).toMatchObject({ classificacao: 0.96, extracao: 0.94, combinado: 0.94, limiar: 0.85, abaixoDoLimiar: false })
    expect(c.formula).toBe('combinado = mín(0,96; 0,94) = 0,94')
  })

  it('ambíguo: abaixo do limiar', () => {
    expect(confiancaDe(CENARIOS_DEMO.ambiguo)?.abaixoDoLimiar).toBe(true)
  })

  it('exatamente no limiar não está abaixo (RF-18 usa "<")', () => {
    const t: TriagemMediFlow = {
      ...RESPOSTAS_ESPERADAS.rotina,
      qualidade: { ...RESPOSTAS_ESPERADAS.rotina.qualidade!, score_combinado: 0.85 },
    }
    expect(confiancaDe(t)?.abaixoDoLimiar).toBe(false)
  })

  it('omite a fórmula quando o combinado não é o mínimo dos dois', () => {
    const t: TriagemMediFlow = {
      ...RESPOSTAS_ESPERADAS.rotina,
      qualidade: { ...RESPOSTAS_ESPERADAS.rotina.qualidade!, score_combinado: 0.5 },
    }
    expect(confiancaDe(t)?.formula).toBeNull()
  })

  it('sem qualidade não há confiança', () => {
    expect(confiancaDe({ ...RESPOSTAS_ESPERADAS.rotina, qualidade: null })).toBeNull()
  })
})

describe('medicamentos', () => {
  it('liga o conflito ao medicamento pelo índice do campo', () => {
    const [conflito] = conflitosDoMedicamento(comDose.qualidade!.conflitos, 0)
    expect(conflito.tipo).toBe('DOSE_SUSPEITA')
    expect(conflitosDoMedicamento(comDose.qualidade!.conflitos, 1)).toEqual([])
    expect(rotuloSinalizacao(conflito)).toBe('Dose suspeita')
  })
})

describe('alertaDeErro', () => {
  it('03e: erro de persistência permite reprocessar', () => {
    const t: TriagemMediFlow = {
      ...RESPOSTAS_ESPERADAS.rotina,
      status: 'ERRO_PERSISTENCIA',
      erro: { codigo: 'ERRO_PERSISTENCIA', mensagem: 'Timeout no bucket' },
    }
    expect(alertaDeErro(t)).toMatchObject({
      titulo: 'Triagem não confirmada · falha ao salvar o resultado',
      podeReprocessar: true,
    })
    expect(alertaDeErro(t)?.codigo).toBe('Etapa: persistencia_resultado · código ERRO_PERSISTENCIA · Timeout no bucket')
  })

  it('erro de processamento não oferece reprocessar', () => {
    const t: TriagemMediFlow = { ...RESPOSTAS_ESPERADAS.rotina, status: 'ERRO_PROCESSAMENTO', erro: null }
    expect(alertaDeErro(t)).toMatchObject({ podeReprocessar: false, codigo: 'código ERRO_PROCESSAMENTO' })
  })

  it('status de sucesso não tem alerta', () => {
    expect(alertaDeErro(RESPOSTAS_ESPERADAS.rotina)).toBeNull()
  })
})

describe('formatação', () => {
  it('CRM estruturado, texto livre e ausente', () => {
    expect(formatarCrm({ numero: '145892', uf: 'SP' })).toBe('145892 / SP')
    expect(formatarCrm({ numero: '145892' })).toBe('145892')
    expect(formatarCrm('112345-SP')).toBe('112345-SP')
    expect(formatarCrm({ numero: null, uf: 'SP' })).toBeNull()
    expect(formatarCrm(null)).toBeNull()
  })

  it('idade e especialidade', () => {
    expect(formatarIdade(52)).toBe('52 anos')
    expect(formatarIdade(1)).toBe('1 ano')
    expect(formatarIdade(null)).toBeNull()
    expect(formatarEspecialidade(['Radiologia', 'Pneumologia'])).toBe('Radiologia, Pneumologia')
    expect(formatarEspecialidade('Radiologia')).toBe('Radiologia')
    expect(formatarEspecialidade([])).toBeNull()
  })

  it('tom do badge do cabeçalho', () => {
    expect(tomDoStatus('PROCESSADO')).toBe('success')
    expect(tomDoStatus('EM_REVISAO')).toBe('warning')
    expect(tomDoStatus('ERRO_PERSISTENCIA')).toBe('error')
  })
})
