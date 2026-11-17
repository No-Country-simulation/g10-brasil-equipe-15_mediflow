import { describe, expect, it } from 'vitest'
import { CENARIOS_DEMO, RESPOSTAS_ESPERADAS } from '../fixtures'
import urgenteRevisao from '../fixtures/expected/urgente_revisao.json'
import type { TriagemMediFlow } from '../types/clinical'
import {
  buscarPorId,
  contadorDocumentos,
  contarFilas,
  ehDoMedicoLogado,
  filaDaUrl,
  filtrarPorFila,
  formatarRecebido,
  linhaDe,
  rotaDaLinha,
  rotuloTipoCurto,
  scoreDaLinha,
} from './filasTriagens'
import type { LinhaTriagem } from './filasTriagens'
import { normalizarTriagem } from './normalizarTriagem'

const base = (id: string) => ({ documentoId: id, canal: 'Ambulatório', enviadoEm: '2026-10-21T13:49:00.000Z' })
const concluida = (id: string, t: TriagemMediFlow) => linhaDe(base(id), t.status, t)

const rotina = concluida('DOC-ROT', RESPOSTAS_ESPERADAS.rotina)
const urgente = concluida('DOC-URG', CENARIOS_DEMO.urgente)
const ambiguo = concluida('DOC-AMB', CENARIOS_DEMO.ambiguo)
const simultaneo = concluida('DOC-SIM', normalizarTriagem(urgenteRevisao.resposta_esperada))
const andamento = linhaDe(base('DOC-AND'), 'PROCESSANDO', null)
const erro = concluida('DOC-ERR', { ...RESPOSTAS_ESPERADAS.rotina, status: 'ERRO_PERSISTENCIA' })
const todas: LinhaTriagem[] = [erro, simultaneo, ambiguo, rotina, urgente, andamento]

describe('linhaDe', () => {
  it('tira tipo, prioridade, destinos, score e CRM do resultado', () => {
    expect(urgente).toMatchObject({
      status: 'PROCESSADO',
      concluida: true,
      tipo: 'LAUDO_EXAME_IMAGEM',
      prioridade: 'URGENTE',
      destinos: ['FILA_URGENCIA_MEDICA'],
      score: 0.98,
      limiar: 0.85,
    })
  })

  it('triagem em andamento fica sem dados do resultado', () => {
    expect(andamento).toMatchObject({ concluida: false, tipo: null, prioridade: null, destinos: [], score: null })
  })

  it('o canal do resultado tem prioridade sobre o do registro', () => {
    const t = { ...RESPOSTAS_ESPERADAS.rotina, canal_origem: 'Internação' }
    expect(concluida('X', t).canal).toBe('Internação')
  })
})

describe('filas', () => {
  it('contagens se sobrepõem como no Figma', () => {
    expect(contarFilas(todas)).toEqual({ todos: 6, urgencia: 2, revisao: 2, processados: 2, andamento: 1, erro: 1 })
  })

  it('urgência inclui o urgente processado e o urgente em revisão', () => {
    expect(filtrarPorFila(todas, 'urgencia').map((l) => l.documentoId)).toEqual(['DOC-SIM', 'DOC-URG'])
  })

  it('revisão inclui EM_REVISAO e quem requer auditoria', () => {
    expect(filtrarPorFila(todas, 'revisao').map((l) => l.documentoId)).toEqual(['DOC-SIM', 'DOC-AMB'])
  })

  it('revisão também pega PROCESSADO com requer_auditoria_humana', () => {
    const auditada = { ...rotina, documentoId: 'DOC-AUD', requerRevisao: true }
    expect(filtrarPorFila([auditada], 'revisao')).toHaveLength(1)
    expect(filtrarPorFila([rotina], 'revisao')).toHaveLength(0)
  })

  it('urgência também pega rotina com destino de urgência', () => {
    const roteada = { ...rotina, destinos: ['FILA_URGENCIA_MEDICA' as const] }
    expect(filtrarPorFila([roteada], 'urgencia')).toHaveLength(1)
  })

  it('lê a fila da URL e cai em "todos" quando é inválida', () => {
    expect(filaDaUrl('revisao')).toBe('revisao')
    expect(filaDaUrl('qualquer')).toBe('todos')
    expect(filaDaUrl(null)).toBe('todos')
  })

  it('busca por parte do ID, sem diferenciar maiúsculas', () => {
    expect(buscarPorId(todas, ' doc-a').map((l) => l.documentoId)).toEqual(['DOC-AMB', 'DOC-AND'])
    expect(buscarPorId(todas, '')).toHaveLength(6)
  })
})

describe('meus documentos', () => {
  const comCrm = (crm: LinhaTriagem['crmMedico']) => ({ ...rotina, crmMedico: crm })

  it('compara o CRM do documento com o da médica logada (145892/SP)', () => {
    expect(ehDoMedicoLogado(comCrm({ numero: '145892', uf: 'SP' }))).toBe(true)
    expect(ehDoMedicoLogado(comCrm('145892-SP'))).toBe(true)
    expect(ehDoMedicoLogado(comCrm('CRM 145.892'))).toBe(true)
    expect(ehDoMedicoLogado(comCrm({ numero: '145892', uf: 'RJ' }))).toBe(false)
    expect(ehDoMedicoLogado(comCrm('98765-SP'))).toBe(false)
    expect(ehDoMedicoLogado(comCrm(null))).toBe(false)
  })

  it('o fixture urgente do catálogo é da Dra. Renata Silveira', () => {
    expect(ehDoMedicoLogado(concluida('X', RESPOSTAS_ESPERADAS.urgente))).toBe(true)
    expect(ehDoMedicoLogado(urgente)).toBe(false)
  })
})

describe('células', () => {
  it('score com aviso de limiar só quando está abaixo', () => {
    expect(scoreDaLinha(rotina)).toEqual({ valor: '0,91', abaixo: null })
    expect(scoreDaLinha(ambiguo)).toEqual({ valor: '0,65', abaixo: 'abaixo de 0,85' })
    expect(scoreDaLinha(andamento)).toBeNull()
  })

  it('recebido: HH:mm hoje, dd/mm HH:mm em outro dia', () => {
    const agora = new Date('2026-10-21T18:00:00.000Z')
    expect(formatarRecebido('2026-10-21T13:49:00.000Z', agora)).toMatch(/^\d{2}:\d{2}$/)
    expect(formatarRecebido('2026-10-19T13:49:00.000Z', agora)).toMatch(/^19\/10 \d{2}:\d{2}$/)
    expect(formatarRecebido('ontem')).toBe('—')
  })

  it('rótulos curtos, contador e destino do "Abrir"', () => {
    expect(rotuloTipoCurto('LAUDO_EXAME_LABORATORIAL')).toBe('Laudo laboratorial')
    expect(rotuloTipoCurto(null)).toBe('—')
    expect(contadorDocumentos(1)).toBe('· 1 documento')
    expect(contadorDocumentos(5)).toBe('· 5 documentos')
    expect(rotaDaLinha(rotina)).toBe('/resultado/DOC-ROT')
    expect(rotaDaLinha(andamento)).toBe('/nova-triagem/processamento/DOC-AND')
  })
})
