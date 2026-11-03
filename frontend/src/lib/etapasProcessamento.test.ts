import { describe, expect, it } from 'vitest'
import {
  badgeDoStatus,
  derivarEtapas,
  etapaVisualPorTempo,
  INTERVALO_AVANCO_MS,
  ROTULO_ESTADO_ETAPA,
  statusTerminal,
} from './etapasProcessamento'

const estados = (p: ReturnType<typeof derivarEtapas>) => p.etapas.map((e) => e.estado)

describe('derivarEtapas', () => {
  it('tem as 8 etapas do Figma, com os títulos exatos', () => {
    const { etapas } = derivarEtapas({ status: 'PROCESSADO' })
    expect(etapas.map((e) => e.titulo)).toEqual([
      'Requisição aceita',
      'Original salvo no OCI',
      'Leitura do conteúdo',
      'Classificação',
      'Extração e validação',
      'Qualidade e conflitos',
      'Decisão de roteamento',
      'Resultado salvo',
    ])
    expect(etapas.map((e) => e.numero)).toEqual([1, 2, 3, 4, 5, 6, 7, 8])
  })

  it('02a: PROCESSANDO com a etapa 5 em andamento dá 4 concluídas e 50%', () => {
    const p = derivarEtapas({ status: 'PROCESSANDO', etapaVisual: 5 })
    expect(estados(p)).toEqual([
      'concluido', 'concluido', 'concluido', 'concluido',
      'andamento', 'aguardando', 'aguardando', 'aguardando',
    ])
    expect(p.concluidas).toBe(4)
    expect(p.porcentagem).toBe(50)
    expect(p.rotuloBarra).toBe('Consultando o status a cada 2 s')
    expect(p.terminal).toBe(false)
  })

  it('PROCESSANDO começa na etapa 3 e limita o marcador visual entre 3 e 7', () => {
    expect(estados(derivarEtapas({ status: 'PROCESSANDO' }))[2]).toBe('andamento')
    expect(estados(derivarEtapas({ status: 'PROCESSANDO', etapaVisual: 1 }))[2]).toBe('andamento')
    const ultima = derivarEtapas({ status: 'PROCESSANDO', etapaVisual: 99 })
    expect(estados(ultima)[6]).toBe('andamento')
    expect(estados(ultima)[7]).toBe('aguardando')
  })

  it('02b: PROCESSADO conclui tudo, 100%, e libera o polling', () => {
    const p = derivarEtapas({ status: 'PROCESSADO' })
    expect(estados(p).every((e) => e === 'concluido')).toBe(true)
    expect(p.porcentagem).toBe(100)
    expect(p.rotuloBarra).toBe('Triagem concluída')
    expect(p.terminal).toBe(true)
  })

  it('EM_REVISAO também conclui todas as etapas', () => {
    const p = derivarEtapas({ status: 'EM_REVISAO' })
    expect(p.porcentagem).toBe(100)
    expect(p.terminal).toBe(true)
  })

  it('RECEBIDO e ainda sem resposta: só a etapa 1 concluída e a 2 em andamento', () => {
    for (const status of ['RECEBIDO', null] as const) {
      const p = derivarEtapas({ status })
      expect(estados(p).slice(0, 3)).toEqual(['concluido', 'andamento', 'aguardando'])
      expect(p.porcentagem).toBe(13)
      expect(p.terminal).toBe(false)
    }
  })

  it('ERRO_PROCESSAMENTO marca como falha a etapa que estava em andamento', () => {
    const p = derivarEtapas({ status: 'ERRO_PROCESSAMENTO', etapaVisual: 4 })
    expect(estados(p)).toEqual([
      'concluido', 'concluido', 'concluido', 'falhou',
      'aguardando', 'aguardando', 'aguardando', 'aguardando',
    ])
    expect(p.rotuloBarra).toBe('Triagem interrompida')
    expect(p.terminal).toBe(true)
  })

  it('ERRO_PERSISTENCIA falha só na última etapa', () => {
    const p = derivarEtapas({ status: 'ERRO_PERSISTENCIA' })
    expect(estados(p).slice(0, 7).every((e) => e === 'concluido')).toBe(true)
    expect(estados(p)[7]).toBe('falhou')
    expect(p.porcentagem).toBe(88)
  })

  it('usa o caminho do resultado (mono) só quando ele é conhecido', () => {
    const sem = derivarEtapas({ status: 'PROCESSADO', caminhoResultado: null }).etapas[7]
    expect(sem.mono).toBe(false)
    expect(sem.subtexto).toMatch(/gravados no OCI/)

    const com = derivarEtapas({ status: 'PROCESSADO', caminhoResultado: 'processados/urgentes/DOC-1.json' }).etapas[7]
    expect(com).toMatchObject({ subtexto: 'processados/urgentes/DOC-1.json', mono: true })
  })

  it('a etapa 1 usa texto mono e a 5 cita o esquema 2.0', () => {
    const { etapas } = derivarEtapas({ status: 'PROCESSADO' })
    expect(etapas[0].mono).toBe(true)
    expect(etapas[4].subtexto).toContain('esquema v2.0')
  })
})

describe('etapaVisualPorTempo', () => {
  it('começa na 3 e avança uma etapa a cada intervalo, parando na 7', () => {
    expect(etapaVisualPorTempo(0)).toBe(3)
    expect(etapaVisualPorTempo(INTERVALO_AVANCO_MS - 1)).toBe(3)
    expect(etapaVisualPorTempo(INTERVALO_AVANCO_MS)).toBe(4)
    expect(etapaVisualPorTempo(INTERVALO_AVANCO_MS * 2)).toBe(5)
    expect(etapaVisualPorTempo(INTERVALO_AVANCO_MS * 100)).toBe(7)
  })

  it('ignora tempo negativo', () => {
    expect(etapaVisualPorTempo(-500)).toBe(3)
  })
})

describe('badgeDoStatus e statusTerminal', () => {
  it('segue o Figma para PROCESSANDO e PROCESSADO', () => {
    expect(badgeDoStatus('PROCESSANDO')).toEqual({ tom: 'info', rotulo: 'PROCESSANDO' })
    expect(badgeDoStatus('PROCESSADO')).toEqual({ tom: 'success', rotulo: 'PROCESSADO' })
  })

  it('cobre revisão, erros e o estado inicial', () => {
    expect(badgeDoStatus('EM_REVISAO').tom).toBe('warning')
    expect(badgeDoStatus('ERRO_PROCESSAMENTO').tom).toBe('error')
    expect(badgeDoStatus('ERRO_PERSISTENCIA').tom).toBe('error')
    expect(badgeDoStatus(null)).toEqual({ tom: 'info', rotulo: 'RECEBIDO' })
  })

  it('só os quatro estados finais são terminais', () => {
    expect(statusTerminal('RECEBIDO')).toBe(false)
    expect(statusTerminal('PROCESSANDO')).toBe(false)
    expect(statusTerminal(null)).toBe(false)
    expect(['PROCESSADO', 'EM_REVISAO', 'ERRO_PROCESSAMENTO', 'ERRO_PERSISTENCIA'].every((s) => statusTerminal(s as never))).toBe(true)
  })

  it('tem rótulo para cada estado da etapa', () => {
    expect(ROTULO_ESTADO_ETAPA).toEqual({
      concluido: 'Concluído',
      andamento: 'Em andamento',
      aguardando: 'Aguardando',
      falhou: 'Falhou',
    })
  })
})
