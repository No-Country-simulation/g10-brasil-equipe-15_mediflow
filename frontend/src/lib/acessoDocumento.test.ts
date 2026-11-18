import { describe, expect, it } from 'vitest'
import { RESPOSTAS_ESPERADAS } from '../fixtures'
import type { TriagemMediFlow } from '../types/clinical'
import { acessoAoDocumento } from './acessoDocumento'

const renata = { nome: 'Dra. Renata Silveira', crm: { numero: '145892', uf: 'SP' } }
const comCrm = (crm: unknown): TriagemMediFlow => ({
  ...RESPOSTAS_ESPERADAS.rotina,
  dados_extraidos: { ...RESPOSTAS_ESPERADAS.rotina.dados_extraidos!, medico: { nome: 'X', crm: crm as never } },
})

describe('acessoAoDocumento (00d)', () => {
  it('bloqueia documento de outro CRM que não foi enviado aqui', () => {
    expect(acessoAoDocumento(comCrm({ numero: '88214', uf: 'RS' }), renata, false)).toEqual({
      permitido: false,
      crmDocumento: 'CRM 88214 / RS',
    })
  })

  it('libera o próprio CRM, em qualquer formato', () => {
    expect(acessoAoDocumento(comCrm({ numero: '145892', uf: 'SP' }), renata, false).permitido).toBe(true)
    expect(acessoAoDocumento(comCrm('145892-SP'), renata, false).permitido).toBe(true)
  })

  it('quem enviou sempre vê o que enviou', () => {
    expect(acessoAoDocumento(comCrm({ numero: '88214', uf: 'RS' }), renata, true).permitido).toBe(true)
  })

  it('documento sem CRM extraído ou sem sessão não é bloqueado', () => {
    expect(acessoAoDocumento(comCrm(null), renata, false).permitido).toBe(true)
    expect(acessoAoDocumento(comCrm({ numero: '88214', uf: 'RS' }), null, false).permitido).toBe(true)
  })
})
