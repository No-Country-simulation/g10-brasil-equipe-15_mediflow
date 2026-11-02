import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, health, submeterTriagemArquivo, submeterTriagemTexto } from './api'

const criada = {
  documento_id: 'DOC-1',
  status: 'RECEBIDO',
  status_url: '/api/v1/triagens/DOC-1/status',
  historico_url: '/api/v1/triagens/DOC-1/historico',
  mensagem: 'ok',
}

function responder(status: number, corpo: unknown) {
  return new Response(JSON.stringify(corpo), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('cliente da API', () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
  })

  it('envia arquivo como multipart com os campos opcionais só quando preenchidos', async () => {
    fetchMock.mockResolvedValue(responder(202, criada))
    const file = new File(['%PDF'], 'laudo.pdf', { type: 'application/pdf' })

    const resposta = await submeterTriagemArquivo({ file, canal_origem: 'Ambulatório' })

    expect(resposta.documento_id).toBe('DOC-1')
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/v1/triagens')
    expect(init.method).toBe('POST')
    const form = init.body as FormData
    expect((form.get('file') as File).name).toBe('laudo.pdf')
    expect(form.get('canal_origem')).toBe('Ambulatório')
    expect(form.has('documento_id')).toBe(false)
  })

  it('envia texto como JSON', async () => {
    fetchMock.mockResolvedValue(responder(202, criada))

    await submeterTriagemTexto({ documento_texto: 'Paciente X', canal_origem: 'Recepção', documento_id: 'MEU-ID' })

    const [, init] = fetchMock.mock.calls[0]
    expect(init.headers['Content-Type']).toBe('application/json')
    expect(JSON.parse(init.body)).toEqual({
      tipo_arquivo: 'TEXTO',
      documento_texto: 'Paciente X',
      canal_origem: 'Recepção',
      documento_id: 'MEU-ID',
    })
  })

  it('converte o envelope de erro da API em ApiError', async () => {
    fetchMock.mockResolvedValue(responder(415, { codigo: 'MIME_INVALIDO', mensagem: 'Conteúdo incompatível.' }))

    const erro = await health().catch((e: unknown) => e)

    expect(erro).toBeInstanceOf(ApiError)
    expect(erro).toMatchObject({ status: 415, codigo: 'MIME_INVALIDO', message: 'Conteúdo incompatível.' })
  })

  it('gera ApiError genérico quando o erro não segue o envelope', async () => {
    fetchMock.mockResolvedValue(new Response('<html>Bad gateway</html>', { status: 502 }))

    await expect(health()).rejects.toMatchObject({ status: 502, codigo: 'ERRO_REQUISICAO' })
  })

  it('gera ApiError REDE quando o servidor está inacessível', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))

    await expect(health()).rejects.toMatchObject({ status: 0, codigo: 'REDE' })
  })
})
