import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NovaTriagemPage } from './NovaTriagemPage'

const criada = {
  documento_id: 'DOC-2026-1',
  status: 'RECEBIDO',
  status_url: '/s',
  historico_url: '/h',
  mensagem: 'ok',
}

function json(status: number, corpo: unknown) {
  return new Response(JSON.stringify(corpo), { status, headers: { 'Content-Type': 'application/json' } })
}

const botaoEnviar = () => screen.getByRole('button', { name: /enviar para triagem|enviando/i })
const pdf = () => new File(['%PDF-1.4 conteudo'], 'laudo.pdf', { type: 'application/pdf' })

describe('NovaTriagemPage', () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
  })

  it('começa com o botão desabilitado e a ajuda da aba Arquivo', () => {
    render(<NovaTriagemPage />)

    expect(botaoEnviar()).toBeDisabled()
    expect(screen.getByText('Selecione um arquivo para enviar.')).toBeInTheDocument()
  })

  it('habilita o envio com um arquivo válido', async () => {
    const user = userEvent.setup()
    render(<NovaTriagemPage />)

    await user.upload(screen.getByLabelText('Selecionar arquivo'), pdf())

    expect(screen.getByText('laudo.pdf')).toBeInTheDocument()
    expect(botaoEnviar()).toBeEnabled()
  })

  it('barra arquivo de formato inválido e mantém o botão desabilitado', async () => {
    const user = userEvent.setup({ applyAccept: false })
    render(<NovaTriagemPage />)

    await user.upload(screen.getByLabelText('Selecionar arquivo'), new File(['x'], 'planilha.docx'))

    expect(screen.getByRole('alert')).toHaveTextContent(/Formato não suportado/)
    expect(botaoEnviar()).toBeDisabled()
  })

  it('habilita o envio na aba Texto só com conteúdo não vazio', async () => {
    const user = userEvent.setup()
    render(<NovaTriagemPage />)

    await user.click(screen.getByRole('button', { name: 'Texto' }))
    const campo = screen.getByLabelText('Conteúdo do documento')
    expect(botaoEnviar()).toBeDisabled()
    expect(screen.getByText('0 caracteres')).toBeInTheDocument()

    await user.type(campo, '   ')
    expect(botaoEnviar()).toBeDisabled()

    await user.type(campo, 'a')
    expect(botaoEnviar()).toBeEnabled()
    expect(screen.getByText('4 caracteres')).toBeInTheDocument()
  })

  it('envia o arquivo, mostra o ID retornado e limpa o formulário', async () => {
    fetchMock.mockResolvedValue(json(202, criada))
    const user = userEvent.setup()
    render(<NovaTriagemPage />)

    await user.upload(screen.getByLabelText('Selecionar arquivo'), pdf())
    await user.type(screen.getByLabelText(/ID do documento/), 'MEU-ID')
    await user.click(botaoEnviar())

    expect(await screen.findByRole('status')).toHaveTextContent('DOC-2026-1')
    const form = fetchMock.mock.calls[0][1].body as FormData
    expect((form.get('file') as File).name).toBe('laudo.pdf')
    expect(form.get('documento_id')).toBe('MEU-ID')
    expect(form.get('canal_origem')).toBe('Pronto-socorro')
    expect(screen.queryByText('laudo.pdf')).not.toBeInTheDocument()
    expect(botaoEnviar()).toBeDisabled()
  })

  it('envia o texto como JSON', async () => {
    fetchMock.mockResolvedValue(json(202, criada))
    const user = userEvent.setup()
    render(<NovaTriagemPage />)

    await user.click(screen.getByRole('button', { name: 'Texto' }))
    await user.type(screen.getByLabelText('Conteúdo do documento'), 'Paciente com dispneia')
    await user.selectOptions(screen.getByLabelText('Canal de origem'), 'Ambulatório')
    await user.click(botaoEnviar())

    await screen.findByRole('status')
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toMatchObject({
      documento_texto: 'Paciente com dispneia',
      canal_origem: 'Ambulatório',
    })
  })

  it('mostra o erro da API e mantém o conteúdo para nova tentativa', async () => {
    fetchMock.mockResolvedValue(json(415, { codigo: 'MIME_INVALIDO', mensagem: 'x' }))
    const user = userEvent.setup()
    render(<NovaTriagemPage />)

    await user.upload(screen.getByLabelText('Selecionar arquivo'), pdf())
    await user.click(botaoEnviar())

    expect(await screen.findByRole('alert')).toHaveTextContent(/não corresponde à extensão/)
    expect(screen.getByText('laudo.pdf')).toBeInTheDocument()
    expect(botaoEnviar()).toBeEnabled()
  })

  it('mostra erro de conexão quando a API está fora do ar', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))
    const user = userEvent.setup()
    render(<NovaTriagemPage />)

    await user.upload(screen.getByLabelText('Selecionar arquivo'), pdf())
    await user.click(botaoEnviar())

    expect(await screen.findByRole('alert')).toHaveTextContent(/Não foi possível conectar à API/)
  })

  it('carrega o PDF de um caso de teste e marca o card como selecionado', async () => {
    fetchMock.mockResolvedValue(new Response('%PDF-1.4', { status: 200 }))
    const user = userEvent.setup()
    render(<NovaTriagemPage />)

    const card = screen.getByRole('button', { name: /Caso urgente/ })
    await user.click(card)

    await waitFor(() => expect(card).toHaveAttribute('aria-pressed', 'true'))
    expect(fetchMock).toHaveBeenCalledWith('/samples/02_laudo_urgencia_tep.pdf')
    expect(screen.getByText('02_laudo_urgencia_tep.pdf')).toBeInTheDocument()
    expect(botaoEnviar()).toBeEnabled()

    await user.click(screen.getByRole('button', { name: 'Remover' }))
    expect(card).toHaveAttribute('aria-pressed', 'false')
  })
})
