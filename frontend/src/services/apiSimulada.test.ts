import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  ATRASO_ENVIO_MS,
  escolherCenario,
  FIM_PROCESSANDO_MS,
  health,
  INICIO_PROCESSANDO_MS,
  limparSimulacao,
  obterHistorico,
  obterStatus,
  obterTriagem,
  submeterTriagemArquivo,
  submeterTriagemTexto,
} from './apiSimulada'

async function enviarTexto(texto: string, extra: { documento_id?: string; canal_origem?: string } = {}) {
  const promessa = submeterTriagemTexto({ documento_texto: texto, ...extra })
  await vi.advanceTimersByTimeAsync(ATRASO_ENVIO_MS)
  return promessa
}

describe('API simulada (modo demo)', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    limparSimulacao()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('escolherCenario', () => {
    it.each([
      ['Matriz_LaudoDeImagem_Texto.pdf', '', 'rotina'],
      ['Matriz_LaudoDeImagem_Pdf.pdf', '', 'urgente'],
      ['Borda_Score_084.pdf', '', 'ambiguo'],
      ['', 'Tromboembolismo pulmonar agudo', 'urgente'],
      ['', 'Lombalgia aguda, score baixo', 'ambiguo'],
      ['', 'Qualquer outro texto', 'rotina'],
    ])('%s / %s → %s', (nome, texto, esperado) => {
      expect(escolherCenario(nome, texto)).toBe(esperado)
    })
  })

  it('aceita o envio com 202, gera ID de demonstração e respeita o ID informado', async () => {
    const gerado = await enviarTexto('qualquer texto')
    expect(gerado.documento_id).toMatch(/^DOC-DEMO-[0-9A-F]{8}$/)
    expect(gerado.status).toBe('RECEBIDO')

    const informado = await enviarTexto('qualquer texto', { documento_id: ' MEU-ID ' })
    expect(informado.documento_id).toBe('MEU-ID')
  })

  it('segue a linha do tempo: RECEBIDO → PROCESSANDO → estado final', async () => {
    const { documento_id: id } = await enviarTexto('Laudo de rotina')

    expect(await obterStatus(id)).toMatchObject({ status: 'RECEBIDO', concluido: false, destinos: [] })

    await vi.advanceTimersByTimeAsync(INICIO_PROCESSANDO_MS)
    expect(await obterStatus(id)).toMatchObject({ status: 'PROCESSANDO', concluido: false })

    await vi.advanceTimersByTimeAsync(FIM_PROCESSANDO_MS - INICIO_PROCESSANDO_MS)
    expect(await obterStatus(id)).toMatchObject({
      status: 'PROCESSADO',
      concluido: true,
      destinos: ['PRONTUARIO_ELETRONICO'],
      requer_auditoria_humana: false,
    })
  })

  it('cenário urgente termina na fila de urgência; ambíguo termina em revisão humana', async () => {
    const urgente = await enviarTexto('Tromboembolismo pulmonar agudo')
    const ambiguo = await enviarTexto('Lombalgia aguda')
    await vi.advanceTimersByTimeAsync(FIM_PROCESSANDO_MS)

    expect(await obterStatus(urgente.documento_id)).toMatchObject({
      status: 'PROCESSADO',
      destinos: ['FILA_URGENCIA_MEDICA'],
    })
    expect(await obterStatus(ambiguo.documento_id)).toMatchObject({
      status: 'EM_REVISAO',
      requer_auditoria_humana: true,
    })
  })

  it('o histórico ganha um evento a cada fase, com horários coerentes', async () => {
    const { documento_id: id } = await enviarTexto('x')

    expect((await obterHistorico(id)).map((e) => e.tipo_evento)).toEqual(['RECEBIDO'])

    await vi.advanceTimersByTimeAsync(INICIO_PROCESSANDO_MS)
    expect((await obterHistorico(id)).map((e) => e.tipo_evento)).toEqual(['RECEBIDO', 'PROCESSANDO'])

    await vi.advanceTimersByTimeAsync(FIM_PROCESSANDO_MS)
    const eventos = await obterHistorico(id)
    expect(eventos.map((e) => e.tipo_evento)).toEqual(['RECEBIDO', 'PROCESSANDO', 'ROTEADO'])
    expect(eventos[2]).toMatchObject({ status_anterior: 'PROCESSANDO', status_novo: 'PROCESSADO' })
    const instantes = eventos.map((e) => Date.parse(e.criado_em))
    expect(instantes).toEqual([...instantes].sort((a, b) => a - b))
  })

  it('o resultado traz o ID e o canal do envio sem alterar o cenário original', async () => {
    const { documento_id: id } = await enviarTexto('Tromboembolismo', { canal_origem: 'Ambulatório' })

    const triagem = await obterTriagem(id)

    expect(triagem).toMatchObject({
      documento_id: id,
      canal_origem: 'Ambulatório',
      status: 'PROCESSADO',
      classificacao: { nivel_prioridade: 'URGENTE' },
    })
    const outra = await obterTriagem(id)
    expect(outra).not.toBe(triagem)
  })

  it('lê o texto de um arquivo .txt para escolher o cenário', async () => {
    const arquivo = new File(['Paciente com lombalgia aguda'], 'nota.txt', { type: 'text/plain' })
    const promessa = submeterTriagemArquivo({ file: arquivo })
    await vi.advanceTimersByTimeAsync(ATRASO_ENVIO_MS)
    const { documento_id: id } = await promessa
    await vi.advanceTimersByTimeAsync(FIM_PROCESSANDO_MS)

    expect((await obterStatus(id)).status).toBe('EM_REVISAO')
  })

  it('sobrevive a um recarregamento (sessionStorage) mas não inventa documentos', async () => {
    const { documento_id: id } = await enviarTexto('x')
    expect(sessionStorage.getItem('mediflow:demo:triagens')).toContain(id)

    await expect(obterStatus('DOC-INEXISTENTE')).rejects.toMatchObject({
      status: 404,
      codigo: 'DOCUMENTO_NAO_ENCONTRADO',
    })
    await expect(obterHistorico('DOC-INEXISTENTE')).rejects.toMatchObject({ status: 404 })
    await expect(obterTriagem('DOC-INEXISTENTE')).rejects.toMatchObject({ status: 404 })
  })

  it('responde ao health check', async () => {
    expect(await health()).toMatchObject({ status: 'healthy', versao: 'demo' })
  })
})
