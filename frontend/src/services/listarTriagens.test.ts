import { beforeEach, describe, expect, it, vi } from 'vitest'
import rotina from '../fixtures/expected/rotina.json'
import { lerRegistro, registrarEnvio } from '../lib/registroTriagens'
import { listarTriagens } from './listarTriagens'

function json(status: number, corpo: unknown) {
  return new Response(JSON.stringify(corpo), { status, headers: { 'Content-Type': 'application/json' } })
}

const envio = (id: string) => ({ documentoId: id, canal: 'Ambulatório', enviadoEm: '2026-10-21T13:49:00.000Z' })

describe('listarTriagens (provisória)', () => {
  const fetchMock = vi.fn()
  let respostas: Record<string, 'PROCESSADO' | 'PROCESSANDO' | 404 | 'REDE'>

  beforeEach(() => {
    localStorage.clear()
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
    fetchMock.mockImplementation(async (url: string) => {
      const id = decodeURIComponent(url.split('/triagens/')[1].split('/')[0])
      const r = respostas[id]
      if (r === 'REDE') throw new TypeError('Failed to fetch')
      if (r === 404) return json(404, { codigo: 'DOCUMENTO_NAO_ENCONTRADO', mensagem: 'x' })
      if (url.endsWith('/status')) return json(200, { documento_id: id, status: r, destinos: [], requer_auditoria_humana: false, concluido: r === 'PROCESSADO' })
      return json(200, { ...rotina.resposta_esperada, documento_id: id })
    })
  })

  it('consulta cada ID registrado e só pede o resultado dos concluídos', async () => {
    registrarEnvio(envio('A'))
    registrarEnvio(envio('B'))
    respostas = { A: 'PROCESSADO', B: 'PROCESSANDO' }

    const linhas = await listarTriagens()

    expect(linhas.map((l) => [l.documentoId, l.status, l.concluida])).toEqual([
      ['B', 'PROCESSANDO', false],
      ['A', 'PROCESSADO', true],
    ])
    expect(fetchMock.mock.calls.map(([u]) => String(u)).filter((u) => !u.endsWith('/status'))).toEqual(['/api/v1/triagens/A'])
  })

  it('remove do registro os IDs que a API não conhece (404)', async () => {
    registrarEnvio(envio('VELHO'))
    registrarEnvio(envio('A'))
    respostas = { A: 'PROCESSADO', VELHO: 404 }

    const linhas = await listarTriagens()

    expect(linhas.map((l) => l.documentoId)).toEqual(['A'])
    expect(lerRegistro().map((e) => e.documentoId)).toEqual(['A'])
  })

  it('falha de rede em um item não derruba a lista nem apaga o registro', async () => {
    registrarEnvio(envio('A'))
    registrarEnvio(envio('B'))
    respostas = { A: 'PROCESSADO', B: 'REDE' }

    expect((await listarTriagens()).map((l) => l.documentoId)).toEqual(['A'])
    expect(lerRegistro()).toHaveLength(2)
  })

  it('se todos falharem por rede, o erro sobe', async () => {
    registrarEnvio(envio('A'))
    respostas = { A: 'REDE' }

    await expect(listarTriagens()).rejects.toMatchObject({ codigo: 'REDE' })
  })

  it('sem envios registrados devolve lista vazia sem chamar a API', async () => {
    respostas = {}
    expect(await listarTriagens()).toEqual([])
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
