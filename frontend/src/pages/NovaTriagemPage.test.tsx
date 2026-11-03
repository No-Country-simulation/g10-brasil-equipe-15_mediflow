import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation, useParams } from 'react-router'
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

/** Stand-in da tela de Processamento: mostra o ID da URL e o estado recebido na navegação. */
function ProcessamentoFalso() {
  const { documentoId } = useParams()
  const { state } = useLocation()
  return (
    <div>
      <p>Processamento de {documentoId}</p>
      <p data-testid="estado">{JSON.stringify(state)}</p>
    </div>
  )
}

function renderPagina() {
  return render(
    <MemoryRouter initialEntries={['/nova-triagem']}>
      <Routes>
        <Route path="/nova-triagem" element={<NovaTriagemPage />} />
        <Route path="/nova-triagem/processamento/:documentoId" element={<ProcessamentoFalso />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('NovaTriagemPage', () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
  })

  it('começa com o botão desabilitado e a ajuda da aba Arquivo', () => {
    renderPagina()

    expect(botaoEnviar()).toBeDisabled()
    expect(screen.getByText('Selecione um arquivo para enviar.')).toBeInTheDocument()
  })

  it('habilita o envio com um arquivo válido', async () => {
    const user = userEvent.setup()
    renderPagina()

    await user.upload(screen.getByLabelText('Selecionar arquivo'), pdf())

    expect(screen.getByText('laudo.pdf')).toBeInTheDocument()
    expect(screen.queryByText(/Processamento de/)).not.toBeInTheDocument()
    expect(botaoEnviar()).toBeEnabled()
  })

  it('barra arquivo de formato inválido e mantém o botão desabilitado', async () => {
    const user = userEvent.setup({ applyAccept: false })
    renderPagina()

    await user.upload(screen.getByLabelText('Selecionar arquivo'), new File(['x'], 'planilha.docx'))

    expect(screen.getByRole('alert')).toHaveTextContent(/Formato não suportado/)
    expect(botaoEnviar()).toBeDisabled()
  })

  it('habilita o envio na aba Texto só com conteúdo não vazio', async () => {
    const user = userEvent.setup()
    renderPagina()

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

  it('envia o arquivo e segue para o processamento com o ID devolvido pela API', async () => {
    fetchMock.mockResolvedValue(json(202, criada))
    const user = userEvent.setup()
    renderPagina()

    await user.upload(screen.getByLabelText('Selecionar arquivo'), pdf())
    await user.type(screen.getByLabelText(/ID do documento/), 'MEU-ID')
    await user.click(botaoEnviar())

    expect(await screen.findByText('Processamento de DOC-2026-1')).toBeInTheDocument()
    const form = fetchMock.mock.calls[0][1].body as FormData
    expect((form.get('file') as File).name).toBe('laudo.pdf')
    expect(form.get('documento_id')).toBe('MEU-ID')
    expect(form.get('canal_origem')).toBe('Pronto-socorro')
    expect(JSON.parse(screen.getByTestId('estado').textContent ?? '')).toMatchObject({
      formato: 'PDF',
      canal: 'Pronto-socorro',
    })
  })

  it('envia o texto como JSON e leva o formato "Texto" e o canal para o processamento', async () => {
    fetchMock.mockResolvedValue(json(202, criada))
    const user = userEvent.setup()
    renderPagina()

    await user.click(screen.getByRole('button', { name: 'Texto' }))
    await user.type(screen.getByLabelText('Conteúdo do documento'), 'Paciente com dispneia')
    await user.selectOptions(screen.getByLabelText('Canal de origem'), 'Ambulatório')
    await user.click(botaoEnviar())

    await screen.findByText('Processamento de DOC-2026-1')
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toMatchObject({
      documento_texto: 'Paciente com dispneia',
      canal_origem: 'Ambulatório',
    })
    const estado = JSON.parse(screen.getByTestId('estado').textContent ?? '')
    expect(estado).toMatchObject({ formato: 'Texto', canal: 'Ambulatório' })
    expect(Number.isNaN(Date.parse(estado.enviadoEm))).toBe(false)
  })

  it('mostra o erro da API e mantém o conteúdo para nova tentativa', async () => {
    fetchMock.mockResolvedValue(json(415, { codigo: 'MIME_INVALIDO', mensagem: 'x' }))
    const user = userEvent.setup()
    renderPagina()

    await user.upload(screen.getByLabelText('Selecionar arquivo'), pdf())
    await user.click(botaoEnviar())

    expect(await screen.findByRole('alert')).toHaveTextContent(/não corresponde à extensão/)
    expect(screen.getByText('laudo.pdf')).toBeInTheDocument()
    expect(screen.queryByText(/Processamento de/)).not.toBeInTheDocument()
    expect(botaoEnviar()).toBeEnabled()
  })

  it('mostra erro de conexão quando a API está fora do ar', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))
    const user = userEvent.setup()
    renderPagina()

    await user.upload(screen.getByLabelText('Selecionar arquivo'), pdf())
    await user.click(botaoEnviar())

    expect(await screen.findByRole('alert')).toHaveTextContent(/Não foi possível conectar à API/)
  })

  it('mostra o destino esperado de cada cenário, lido dos fixtures', () => {
    renderPagina()

    expect(screen.getByRole('button', { name: /Fluxo padrão/ })).toHaveTextContent('Esperado: Prontuário eletrônico')
    expect(screen.getByRole('button', { name: /Caso urgente/ })).toHaveTextContent('Esperado: Fila de urgência + alerta')
    expect(screen.getByRole('button', { name: /Caso ambíguo/ })).toHaveTextContent('Esperado: Fila de revisão humana')
  })

  it('carrega o PDF do fluxo padrão na aba Arquivo e marca o card como selecionado', async () => {
    fetchMock.mockResolvedValue(new Response('%PDF-1.4', { status: 200 }))
    const user = userEvent.setup()
    renderPagina()

    const card = screen.getByRole('button', { name: /Fluxo padrão/ })
    await user.click(card)

    await waitFor(() => expect(card).toHaveAttribute('aria-pressed', 'true'))
    expect(fetchMock).toHaveBeenCalledWith('/samples/rotina/Matriz_LaudoDeImagem_Texto.pdf')
    expect(screen.getByText('Matriz_LaudoDeImagem_Texto.pdf')).toBeInTheDocument()
    expect(botaoEnviar()).toBeEnabled()

    await user.click(screen.getByRole('button', { name: 'Remover' }))
    expect(card).toHaveAttribute('aria-pressed', 'false')
  })

  it('carrega o caso urgente como texto, na aba Texto', async () => {
    fetchMock.mockResolvedValue(new Response('LAUDO DE TOMOGRAFIA\nTromboembolismo pulmonar agudo', { status: 200 }))
    const user = userEvent.setup()
    renderPagina()

    const card = screen.getByRole('button', { name: /Caso urgente/ })
    await user.click(card)

    await waitFor(() => expect(card).toHaveAttribute('aria-pressed', 'true'))
    expect(fetchMock).toHaveBeenCalledWith('/samples/urgente/Matriz_LaudoDeImagem_Pdf.txt')
    expect(screen.getByLabelText('Conteúdo do documento')).toHaveValue(
      'LAUDO DE TOMOGRAFIA\nTromboembolismo pulmonar agudo',
    )
    expect(botaoEnviar()).toBeEnabled()
  })

  it('envia o caso urgente como JSON de texto', async () => {
    fetchMock.mockResolvedValueOnce(new Response('Tromboembolismo pulmonar agudo', { status: 200 }))
    fetchMock.mockResolvedValueOnce(json(202, criada))
    const user = userEvent.setup()
    renderPagina()

    await user.click(screen.getByRole('button', { name: /Caso urgente/ }))
    await waitFor(() => expect(botaoEnviar()).toBeEnabled())
    await user.click(botaoEnviar())

    await screen.findByText(/DOC-2026-1/)
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toMatchObject({
      documento_texto: 'Tromboembolismo pulmonar agudo',
    })
  })

  it('trocar de caso texto para caso arquivo limpa o texto', async () => {
    fetchMock.mockResolvedValueOnce(new Response('texto do TEP', { status: 200 }))
    fetchMock.mockResolvedValueOnce(new Response('%PDF-1.4', { status: 200 }))
    const user = userEvent.setup()
    renderPagina()

    await user.click(screen.getByRole('button', { name: /Caso urgente/ }))
    await waitFor(() => expect(screen.getByLabelText('Conteúdo do documento')).toHaveValue('texto do TEP'))

    await user.click(screen.getByRole('button', { name: /Caso ambíguo/ }))
    await waitFor(() => expect(screen.getByText('Borda_Score_084.pdf')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: 'Texto' }))
    expect(screen.getByLabelText('Conteúdo do documento')).toHaveValue('')
  })
})
