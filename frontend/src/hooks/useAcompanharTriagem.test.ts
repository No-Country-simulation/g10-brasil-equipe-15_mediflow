import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { INTERVALO_POLLING_MS, MAX_FALHAS_SEGUIDAS, useAcompanharTriagem } from './useAcompanharTriagem'

type StatusApi = 'RECEBIDO' | 'PROCESSANDO' | 'PROCESSADO' | 'EM_REVISAO' | 'ERRO_PROCESSAMENTO'

function json(status: number, corpo: unknown) {
  return new Response(JSON.stringify(corpo), { status, headers: { 'Content-Type': 'application/json' } })
}

const statusDe = (status: StatusApi) => ({
  documento_id: 'DOC-1',
  status,
  destinos: [],
  requer_auditoria_humana: false,
  concluido: status === 'PROCESSADO' || status === 'EM_REVISAO' || status === 'ERRO_PROCESSAMENTO',
})

const evento = (tipo: string, statusNovo: string, extra: object = {}) => ({
  evento_id: `E-${tipo}`,
  documento_id: 'DOC-1',
  tipo_evento: tipo,
  criado_em: '2026-10-21T10:47:00+00:00',
  ator: 'TESTE',
  status_novo: statusNovo,
  versao_esquema: '2.0.0',
  ...extra,
})

describe('useAcompanharTriagem', () => {
  const fetchMock = vi.fn()
  /** Sequência de respostas de /status; a última se repete. */
  let sequencia: Array<StatusApi | 'REDE' | 404 | 500> = []
  let passo = 0
  let historico: unknown[] = []
  let resultadoOk = true

  const chamadas = (sufixo: string) =>
    fetchMock.mock.calls.filter(([url]) => String(url).endsWith(sufixo)).length

  beforeEach(() => {
    vi.useFakeTimers()
    sequencia = ['PROCESSADO']
    passo = 0
    historico = [evento('RECEBIDO', 'RECEBIDO')]
    resultadoOk = true
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
    fetchMock.mockImplementation(async (url: string) => {
      if (url.endsWith('/status')) {
        const item = sequencia[Math.min(passo, sequencia.length - 1)]
        passo += 1
        if (item === 'REDE') throw new TypeError('Failed to fetch')
        if (item === 404) return json(404, { codigo: 'DOCUMENTO_NAO_ENCONTRADO', mensagem: 'Documento não encontrado.' })
        if (item === 500) return json(500, { codigo: 'ERRO_INTERNO', mensagem: 'x' })
        return json(200, statusDe(item))
      }
      if (url.endsWith('/historico')) return json(200, historico)
      return resultadoOk ? json(200, { documento_id: 'DOC-1', status: 'PROCESSADO' }) : json(500, { codigo: 'X', mensagem: 'x' })
    })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  const avancar = (ms: number) => act(() => vi.advanceTimersByTimeAsync(ms))

  it('consulta o status a cada 2 s e para ao chegar num estado final', async () => {
    sequencia = ['RECEBIDO', 'PROCESSANDO', 'PROCESSANDO', 'PROCESSADO']
    const { result } = renderHook(() => useAcompanharTriagem('DOC-1'))

    await avancar(0)
    expect(result.current.status).toBe('RECEBIDO')
    expect(result.current.terminal).toBe(false)

    await avancar(INTERVALO_POLLING_MS)
    expect(result.current.status).toBe('PROCESSANDO')

    await avancar(INTERVALO_POLLING_MS * 2)
    expect(result.current.status).toBe('PROCESSADO')
    expect(result.current.terminal).toBe(true)

    const antes = chamadas('/status')
    await avancar(INTERVALO_POLLING_MS * 5)
    expect(chamadas('/status')).toBe(antes)
  })

  it('lê o histórico só quando o status muda', async () => {
    sequencia = ['PROCESSANDO', 'PROCESSANDO', 'PROCESSANDO', 'PROCESSADO']
    renderHook(() => useAcompanharTriagem('DOC-1'))

    await avancar(INTERVALO_POLLING_MS * 3)

    // PROCESSANDO (1x) e PROCESSADO (1x).
    expect(chamadas('/historico')).toBe(2)
  })

  it('só busca o resultado completo depois de concluída, e uma vez', async () => {
    sequencia = ['PROCESSANDO', 'PROCESSANDO', 'PROCESSADO']
    const { result } = renderHook(() => useAcompanharTriagem('DOC-1'))

    await avancar(INTERVALO_POLLING_MS)
    expect(fetchMock.mock.calls.some(([u]) => String(u).endsWith('/DOC-1'))).toBe(false)
    expect(result.current.resultado).toBeNull()

    await avancar(INTERVALO_POLLING_MS)
    expect(result.current.resultado).toMatchObject({ documento_id: 'DOC-1' })
    expect(fetchMock.mock.calls.filter(([u]) => String(u).endsWith('/DOC-1'))).toHaveLength(1)
  })

  it('falha ao buscar o resultado não vira erro da tela', async () => {
    resultadoOk = false
    const { result } = renderHook(() => useAcompanharTriagem('DOC-1'))

    await avancar(0)

    expect(result.current.status).toBe('PROCESSADO')
    expect(result.current.resultado).toBeNull()
    expect(result.current.erro).toBeNull()
  })

  it('avança o marcador visual de 3 até 7 enquanto processa', async () => {
    sequencia = ['PROCESSANDO']
    const { result } = renderHook(() => useAcompanharTriagem('DOC-1'))

    await avancar(0)
    expect(result.current.etapaVisual).toBe(3)

    await avancar(4000)
    expect(result.current.etapaVisual).toBe(4)

    await avancar(60_000)
    expect(result.current.etapaVisual).toBe(7)
  })

  it('mantém a etapa visual quando termina em erro', async () => {
    sequencia = ['PROCESSANDO', 'PROCESSANDO', 'PROCESSANDO', 'ERRO_PROCESSAMENTO']
    historico = [
      evento('RECEBIDO', 'RECEBIDO'),
      evento('ERRO_PROCESSAMENTO', 'ERRO_PROCESSAMENTO', { motivo: 'Gemini indisponível' }),
    ]
    const { result } = renderHook(() => useAcompanharTriagem('DOC-1'))

    await avancar(INTERVALO_POLLING_MS * 3)

    expect(result.current.status).toBe('ERRO_PROCESSAMENTO')
    expect(result.current.etapaVisual).toBe(3)
    expect(result.current.motivoErro).toBe('Gemini indisponível')
  })

  it('expõe a hora do envio a partir do evento RECEBIDO', async () => {
    const { result } = renderHook(() => useAcompanharTriagem('DOC-1'))

    await avancar(0)

    expect(result.current.enviadoEm).toBe('2026-10-21T10:47:00+00:00')
  })

  it('documento inexistente (404) é erro imediato e não repete', async () => {
    sequencia = [404]
    const { result } = renderHook(() => useAcompanharTriagem('DOC-X'))

    await avancar(0)
    expect(result.current.erro).toMatchObject({ codigo: 'DOCUMENTO_NAO_ENCONTRADO' })
    expect(result.current.erro?.mensagem).toMatch(/Documento não encontrado/)

    await avancar(INTERVALO_POLLING_MS * 5)
    expect(chamadas('/status')).toBe(1)
  })

  it(`tolera ${MAX_FALHAS_SEGUIDAS - 1} falhas de rede seguidas`, async () => {
    sequencia = ['REDE', 'REDE', 'PROCESSADO']
    const { result } = renderHook(() => useAcompanharTriagem('DOC-1'))

    await avancar(INTERVALO_POLLING_MS * 2)

    expect(result.current.erro).toBeNull()
    expect(result.current.status).toBe('PROCESSADO')
  })

  it(`mostra erro depois de ${MAX_FALHAS_SEGUIDAS} falhas seguidas e para de consultar`, async () => {
    sequencia = ['REDE']
    const { result } = renderHook(() => useAcompanharTriagem('DOC-1'))

    await avancar(INTERVALO_POLLING_MS * MAX_FALHAS_SEGUIDAS)

    expect(result.current.erro).toMatchObject({ codigo: 'REDE' })
    const total = chamadas('/status')
    expect(total).toBe(MAX_FALHAS_SEGUIDAS)

    await avancar(INTERVALO_POLLING_MS * 5)
    expect(chamadas('/status')).toBe(total)
  })

  it('erro 5xx também conta como falha transitória', async () => {
    sequencia = [500, 'PROCESSADO']
    const { result } = renderHook(() => useAcompanharTriagem('DOC-1'))

    await avancar(INTERVALO_POLLING_MS)

    expect(result.current.erro).toBeNull()
    expect(result.current.status).toBe('PROCESSADO')
  })

  it('tentarNovamente recomeça depois de um erro', async () => {
    sequencia = ['REDE', 'REDE', 'REDE', 'PROCESSADO']
    const { result } = renderHook(() => useAcompanharTriagem('DOC-1'))
    await avancar(INTERVALO_POLLING_MS * MAX_FALHAS_SEGUIDAS)
    expect(result.current.erro).not.toBeNull()

    act(() => result.current.tentarNovamente())
    await avancar(0)

    expect(result.current.erro).toBeNull()
    expect(result.current.status).toBe('PROCESSADO')
  })

  it('cancela a consulta ao desmontar', async () => {
    sequencia = ['PROCESSANDO']
    const { unmount } = renderHook(() => useAcompanharTriagem('DOC-1'))
    await avancar(INTERVALO_POLLING_MS)
    unmount()
    const total = chamadas('/status')

    await avancar(INTERVALO_POLLING_MS * 5)

    expect(chamadas('/status')).toBe(total)
  })

  it('ao trocar de documento descarta o estado do anterior', async () => {
    sequencia = ['PROCESSADO']
    const { result, rerender } = renderHook(({ id }) => useAcompanharTriagem(id), { initialProps: { id: 'DOC-1' } })
    await avancar(0)
    expect(result.current.status).toBe('PROCESSADO')
    expect(result.current.resultado).not.toBeNull()

    sequencia = ['RECEBIDO']
    passo = 0
    rerender({ id: 'DOC-2' })
    expect(result.current.status).toBeNull()
    expect(result.current.resultado).toBeNull()

    await avancar(0)
    expect(result.current.status).toBe('RECEBIDO')
  })

  it('sem ID não consulta nada', async () => {
    renderHook(() => useAcompanharTriagem(undefined))

    await avancar(INTERVALO_POLLING_MS * 3)

    expect(fetchMock).not.toHaveBeenCalled()
  })
})
