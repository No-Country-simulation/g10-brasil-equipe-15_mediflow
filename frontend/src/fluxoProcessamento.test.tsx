import { act, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { limparSimulacao, FIM_PROCESSANDO_MS, INICIO_PROCESSANDO_MS, ATRASO_ENVIO_MS } from './services/apiSimulada'

/**
 * Fluxo completo da Fase 2 no modo demo, sem mocks da API: Nova triagem → Processamento → Resultado.
 * Os cliques usam fireEvent porque o userEvent trava com os timers falsos do Vitest.
 */

const avancar = (ms: number) => act(() => vi.advanceTimersByTimeAsync(ms))
const clicar = (elemento: HTMLElement) => fireEvent.click(elemento)

function abrir(rota = '/nova-triagem') {
  return render(
    <MemoryRouter initialEntries={[rota]}>
      <App />
    </MemoryRouter>,
  )
}

/** Escolhe um caso de teste, envia e espera a tela de Processamento. */
async function enviarCaso(titulo: RegExp) {
  clicar(screen.getByRole('button', { name: titulo }))
  await avancar(0)
  clicar(screen.getByRole('button', { name: /enviar para triagem/i }))
  await avancar(ATRASO_ENVIO_MS)
  return screen.getByText(/^DOC-DEMO-[0-9A-F]{8}$/).textContent as string
}

describe('fluxo de processamento (modo demo)', () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    vi.useFakeTimers()
    vi.stubEnv('VITE_USAR_FIXTURES', 'true')
    limparSimulacao()
    fetchMock.mockReset()
    // Só os documentos de exemplo de public/samples passam por fetch no modo demo.
    fetchMock.mockImplementation(async (url: string) =>
      url.endsWith('.txt')
        ? new Response('LAUDO DE TOMOGRAFIA\nTromboembolismo pulmonar agudo', { status: 200 })
        : new Response('%PDF-1.4', { status: 200 }),
    )
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllEnvs()
  })

  it('caso urgente: envia como texto, acompanha e termina na fila de urgência', async () => {
    abrir()
    await enviarCaso(/Caso urgente/)

    // Tela de Processamento, recém-enviada.
    expect(screen.getByRole('heading', { name: 'Status da triagem' })).toBeInTheDocument()
    expect(screen.getByText('RECEBIDO')).toBeInTheDocument()
    expect(screen.getByText('Formato').nextElementSibling).toHaveTextContent('Texto')
    expect(screen.getByText('Canal').nextElementSibling).toHaveTextContent('Pronto-socorro')
    expect(screen.getByText('Resposta').nextElementSibling).toHaveTextContent('202 Accepted')
    expect(screen.queryByRole('button', { name: 'Ver resultado' })).not.toBeInTheDocument()

    await avancar(INICIO_PROCESSANDO_MS)
    expect(screen.getByText('PROCESSANDO')).toBeInTheDocument()
    expect(screen.getByText('Em andamento')).toBeInTheDocument()

    await avancar(FIM_PROCESSANDO_MS)
    expect(screen.getByText('PROCESSADO')).toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '100')
    expect(screen.getAllByText('Concluído')).toHaveLength(8)

    clicar(screen.getByRole('button', { name: 'Ver resultado' }))
    expect(screen.getByRole('heading', { name: 'Resultado da triagem' })).toBeInTheDocument()
  })

  it('caso de rotina: envia o PDF e conclui em PROCESSADO', async () => {
    abrir()
    await enviarCaso(/Fluxo padrão/)
    expect(screen.getByText('Formato').nextElementSibling).toHaveTextContent('PDF')

    await avancar(FIM_PROCESSANDO_MS + INICIO_PROCESSANDO_MS)

    expect(screen.getByText('PROCESSADO')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Ver resultado' })).toBeInTheDocument()
  })

  it('caso ambíguo: termina em EM REVISÃO e ainda libera o resultado', async () => {
    abrir()
    await enviarCaso(/Caso ambíguo/)

    await avancar(FIM_PROCESSANDO_MS + INICIO_PROCESSANDO_MS)

    expect(screen.getByText('EM REVISÃO')).toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '100')
    expect(screen.getByRole('button', { name: 'Ver resultado' })).toBeInTheDocument()
  })

  it('a barra lateral mantém "Nova triagem" ativo durante o processamento', async () => {
    abrir()
    await enviarCaso(/Fluxo padrão/)

    // "Nova triagem" é também o link "Voltar"; só o item da barra lateral recebe aria-current.
    const ativos = screen.getAllByRole('link').filter((link) => link.getAttribute('aria-current') === 'page')
    expect(ativos.map((link) => link.textContent)).toEqual(['Nova triagem'])
    // "Triagens e filas" aparece na barra lateral e no aviso "Pode sair desta tela"; nenhum está ativo.
    for (const link of screen.getAllByRole('link', { name: 'Triagens e filas' })) {
      expect(link).not.toHaveAttribute('aria-current')
    }
  })

  it('os avanços das etapas 3 a 7 acontecem enquanto processa e a lista só tem uma etapa atual', async () => {
    abrir()
    await enviarCaso(/Fluxo padrão/)
    await avancar(INICIO_PROCESSANDO_MS)

    const atual = () =>
      screen.getAllByRole('listitem').filter((li) => li.getAttribute('aria-current') === 'step')
    expect(atual()).toHaveLength(1)
    expect(atual()[0]).toHaveTextContent('Leitura do conteúdo')

    await avancar(4000)
    expect(atual()).toHaveLength(1)
    expect(atual()[0]).toHaveTextContent('Classificação')
  })

  it('"Simular de novo" volta para a Nova triagem com o formulário limpo', async () => {
    abrir()
    await enviarCaso(/Fluxo padrão/)

    clicar(screen.getByRole('button', { name: 'Simular de novo' }))

    expect(screen.getByRole('heading', { name: 'Nova triagem' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /enviar para triagem/i })).toBeDisabled()
  })

  it('recarregar a página de processamento continua a acompanhar a mesma triagem', async () => {
    const primeira = abrir()
    const id = await enviarCaso(/Caso ambíguo/)
    primeira.unmount()

    abrir(`/nova-triagem/processamento/${id}`)
    await avancar(FIM_PROCESSANDO_MS + INICIO_PROCESSANDO_MS)

    expect(screen.getByText(id)).toBeInTheDocument()
    expect(screen.getByText('EM REVISÃO')).toBeInTheDocument()
    // Sem o estado da navegação, o card Envio não sabe o formato.
    expect(screen.getByText('Formato').nextElementSibling).toHaveTextContent('—')
  })

  it('um ID que não existe mostra "Documento não encontrado" e nenhuma etapa avança', async () => {
    abrir('/nova-triagem/processamento/DOC-NAO-EXISTE')
    await avancar(0)

    expect(screen.getByRole('alert')).toHaveTextContent(/Documento não encontrado/)
    expect(screen.queryByRole('button', { name: 'Ver resultado' })).not.toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '13')
  })

  it('no modo demo nenhuma chamada de rede para a API é feita', async () => {
    abrir()
    await enviarCaso(/Caso urgente/)
    await avancar(FIM_PROCESSANDO_MS + INICIO_PROCESSANDO_MS)

    const urlsDaApi = fetchMock.mock.calls.map(([url]) => String(url)).filter((url) => url.includes('/api/'))
    expect(urlsDaApi).toEqual([])
  })
})
