import { describe, expect, it } from 'vitest'
import { CENARIOS_DEMO, RESPOSTAS_ESPERADAS } from '../fixtures'
import conflitoDose from '../fixtures/expected/conflito_dose.json'
import urgenteRevisao from '../fixtures/expected/urgente_revisao.json'
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
  motivosDaRevisao,
  rotuloSinalizacao,
  situacaoDoCampo,
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
