import { describe, expect, it } from 'vitest'
import { CENARIOS_DEMO, RESPOSTAS_ESPERADAS } from '../fixtures'
import { normalizarTriagem } from './normalizarTriagem'

describe('normalizarTriagem — cenários da demo (formato anterior)', () => {
  it('rotina: raio-X processado e enviado ao prontuário', () => {
    const t = CENARIOS_DEMO.rotina
    expect(t.status).toBe('PROCESSADO')
    expect(t.documento_id).toBe('DOC-2026-001')
    expect(t.classificacao?.nivel_prioridade).toBe('ROTINA')
    expect(t.classificacao?.score_classificacao).toBe(0.96)
    expect(t.dados_extraidos?.medico).toEqual({ nome: 'Dr. Roberto Mendes', crm: '112345-SP' })
    expect(t.dados_extraidos?.diagnostico).toMatch(/limites da normalidade/)
    expect(t.dados_extraidos?.exames).toEqual(['RADIOGRAFIA DE TÓRAX (PA E PERFIL)'])
    expect(t.dados_extraidos?.urgencia).toBe('NAO')
    expect(t.decisao_roteamento?.destino_principal).toBe('PRONTUARIO_ELETRONICO')
    expect(t.decisao_roteamento?.notificacao).toBeNull()
    expect(t.qualidade?.score_combinado).toBe(0.94)
  })

  it('urgência: TEP agudo vai à fila de urgência com alerta', () => {
    const t = CENARIOS_DEMO.urgente
    expect(t.classificacao?.nivel_prioridade).toBe('URGENTE')
    expect(t.dados_extraidos?.cid).toBe('I26.9')
    expect(t.dados_extraidos?.urgencia).toBe('SIM')
    expect(t.decisao_roteamento?.destino_principal).toBe('FILA_URGENCIA_MEDICA')
    expect(t.decisao_roteamento?.notificacao).toMatchObject({
      gerada: true,
      canal: 'SIMULADO_SLACK_PLANTAO',
      status: 'REGISTRADA',
    })
    expect(t.decisao_roteamento?.notificacao?.mensagem).toContain('DOC-2026-002')
  })

  it('ambiguidade: score abaixo do limiar fica em revisão humana', () => {
    const t = CENARIOS_DEMO.ambiguo
    expect(t.status).toBe('EM_REVISAO')
    expect(t.qualidade?.score_combinado).toBeLessThan(t.qualidade?.limiar_aplicado ?? 0)
    expect(t.qualidade?.campos_ausentes).toEqual(['medico_solicitante.nome', 'medico_solicitante.crm'])
    expect(t.decisao_roteamento?.requer_auditoria_humana).toBe(true)
    expect(t.decisao_roteamento?.destino_principal).toBe('FILA_REVISAO_HUMANA')
    expect(t.decisao_roteamento?.destinos).toEqual(['FILA_REVISAO_HUMANA', 'FARMACIA_HOSPITALAR'])
  })

  it('preenche os campos obrigatórios do tipo que o formato anterior não tem', () => {
    const t = CENARIOS_DEMO.rotina
    expect(t.dados_extraidos?.inconsistencias_detectadas).toEqual([])
    expect(t.armazenamento_oci?.modo_simulacao).toBe(true)
    expect(t.versao_esquema).toBe('desconhecida')
  })
})

describe('normalizarTriagem — contrato atual (expected.json)', () => {
  it('mantém o que já está no contrato', () => {
    const t = RESPOSTAS_ESPERADAS.urgente
    expect(t.status).toBe('PROCESSADO')
    expect(t.classificacao?.especialidade).toEqual(['Radiologia', 'Pneumologia'])
    expect(t.dados_extraidos?.medico.crm).toEqual({ numero: '145892', uf: 'SP' })
    expect(t.decisao_roteamento?.destino_principal).toBe('FILA_URGENCIA_MEDICA')
    expect(t.decisao_roteamento?.notificacao?.gerada).toBe(true)
  })

  it('rotina e ambiguidade batem com o manifesto', () => {
    expect(RESPOSTAS_ESPERADAS.rotina.decisao_roteamento?.destinos).toEqual(['PRONTUARIO_ELETRONICO'])
    expect(RESPOSTAS_ESPERADAS.ambiguo.status).toBe('EM_REVISAO')
    expect(RESPOSTAS_ESPERADAS.ambiguo.qualidade?.score_combinado).toBe(0.84)
  })

  it('é idempotente: normalizar duas vezes dá o mesmo resultado', () => {
    for (const t of Object.values(RESPOSTAS_ESPERADAS)) {
      expect(normalizarTriagem(t)).toEqual(t)
    }
  })
})

describe('normalizarTriagem — entradas inválidas', () => {
  const base = { status: 'PROCESSADO', documento_id: 'X' }

  it('recusa entrada que não é objeto', () => {
    expect(() => normalizarTriagem(null)).toThrow(/objeto/)
    expect(() => normalizarTriagem([])).toThrow(/objeto/)
  })

  it('recusa status, prioridade e destino desconhecidos', () => {
    expect(() => normalizarTriagem({ ...base, status: 'FEITO' })).toThrow(/status/)
    expect(() =>
      normalizarTriagem({ ...base, classificacao: { tipo_documento: 'OUTRO', nivel_prioridade: 'Alta' } }),
    ).toThrow(/nivel_prioridade/)
    expect(() =>
      normalizarTriagem({ ...base, decisao_roteamento: { destino_principal: 'Cozinha', destinos: [] } }),
    ).toThrow(/destino_principal/)
  })

  it('aceita acento, caixa e apelidos de destino', () => {
    const t = normalizarTriagem({
      ...base,
      decisao_roteamento: { destino_principal: 'Prontuário', destinos: ['Fila_Emergencia_Medica'] },
    })
    expect(t.decisao_roteamento?.destino_principal).toBe('PRONTUARIO_ELETRONICO')
    expect(t.decisao_roteamento?.destinos).toEqual(['FILA_URGENCIA_MEDICA'])
  })

  it('usa crm_detalhado quando existe, no lugar do texto livre', () => {
    const t = normalizarTriagem({
      ...base,
      dados_extraidos: {
        medico_solicitante: { nome: 'Dra. A', crm: '1-SP', crm_detalhado: { numero: '1', uf: 'SP' } },
      },
    })
    expect(t.dados_extraidos?.medico.crm).toEqual({ numero: '1', uf: 'SP' })
  })
})
