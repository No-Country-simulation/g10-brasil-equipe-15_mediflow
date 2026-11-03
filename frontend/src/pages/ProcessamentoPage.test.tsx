import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { INTERVALO_POLLING_MS } from '../hooks/useAcompanharTriagem'
import { ProcessamentoPage } from './ProcessamentoPage'

function json(status: number, corpo: unknown) {
  return new Response(JSON.stringify(corpo), { status, headers: { 'Content-Type': 'application/json' } })
}

const statusDe = (status: string) => ({
  documento_id: 'DOC-CLIN-2026-8942',
  status,
  destinos: [],
  requer_auditoria_humana: status === 'EM_REVISAO',
  concluido: ['PROCESSADO', 'EM_REVISAO', 'ERRO_PROCESSAMENTO', 'ERRO_PERSISTENCIA'].includes(status),
})

describe('ProcessamentoPage', () => {
  const fetchMock = vi.fn()
  let sequencia: Array<string | 404 | 'REDE'> = []
  let passo = 0
  let historico: unknown[] = []
  let oci: string | null = null

  beforeEach(() => {
    vi.useFakeTimers()
    sequencia = ['PROCESSADO']
    passo = 0
    historico = []
    oci = null
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
    fetchMock.mockImplementation(async (url: string) => {
      if (url.endsWith('/status')) {
        const item = sequencia[Math.min(passo, sequencia.length - 1)]
        passo += 1
        if (item === 'REDE') throw new TypeError('Failed to fetch')
        if (item === 404) return json(404, { codigo: 'DOCUMENTO_NAO_ENCONTRADO', mensagem: 'Documento não encontrado.' })
        return json(200, statusDe(item))
      }
      if (url.endsWith('/historico')) return json(200, historico)
      return json(200, {
        documento_id: 'DOC-CLIN-2026-8942',
        status: 'PROCESSADO',
        armazenamento_oci: oci ? { bucket: 'b', caminho_objeto: oci, status_backup: 'sucesso', modo_simulacao: true } : null,
      })
    })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  /** Os cliques usam fireEvent: o userEvent não reconhece os timers falsos do Vitest e trava. */
  async function abrir(estado?: unknown) {
    render(
      <MemoryRouter initialEntries={[{ pathname: '/nova-triagem/processamento/DOC-CLIN-2026-8942', state: estado }]}>
        <Routes>
          <Route path="/nova-triagem" element={<p>Tela Nova triagem</p>} />
          <Route path="/nova-triagem/processamento/:documentoId" element={<ProcessamentoPage />} />
          <Route path="/resultado/:documentoId" element={<p>Tela Resultado</p>} />
        </Routes>
      </MemoryRouter>,
    )
    await avancar(0)
  }

  const avancar = (ms: number) => act(() => vi.advanceTimersByTimeAsync(ms))
  const botao = (nome: string) => screen.getByRole('button', { name: nome })

  it('02a: mostra o ID, o badge PROCESSANDO, 50% e só "Simular de novo"', async () => {
    sequencia = ['PROCESSANDO']
    await abrir()
    await avancar(4000 * 2)

    expect(screen.getByRole('heading', { name: 'Status da triagem' })).toBeInTheDocument()
    expect(screen.getByText('DOC-CLIN-2026-8942')).toHaveClass('font-mono')
    expect(screen.getByText('PROCESSANDO')).toBeInTheDocument()
    expect(screen.getByText('Consultando o status a cada 2 s')).toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '50')
    expect(within(screen.getByRole('list', { name: 'Etapas da triagem' })).getAllByRole('listitem')).toHaveLength(8)
    expect(screen.getAllByText('Concluído')).toHaveLength(4)
    expect(screen.getByText('Em andamento')).toBeInTheDocument()
    expect(botao('Simular de novo')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Ver resultado' })).not.toBeInTheDocument()
  })

  it('02b: ao concluir mostra PROCESSADO, 100% e "Ver resultado"', async () => {
    sequencia = ['PROCESSANDO', 'PROCESSADO']
    await abrir()
    await avancar(INTERVALO_POLLING_MS)

    expect(screen.getByText('PROCESSADO')).toBeInTheDocument()
    expect(screen.getByText('Triagem concluída')).toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '100')
    expect(screen.getAllByText('Concluído')).toHaveLength(8)
    expect(botao('Ver resultado')).toBeInTheDocument()
    expect(botao('Simular de novo')).toBeInTheDocument()
  })

  it('mostra o caminho do resultado salvo quando a API o informa', async () => {
    oci = 'processados/urgentes/DOC-CLIN-2026-8942.json'
    await abrir()

    expect(screen.getByText('processados/urgentes/DOC-CLIN-2026-8942.json')).toBeInTheDocument()
  })

  it('EM_REVISAO usa o tom de aviso e também libera o resultado', async () => {
    sequencia = ['EM_REVISAO']
    await abrir()

    expect(screen.getByText('EM REVISÃO')).toBeInTheDocument()
    expect(botao('Ver resultado')).toBeInTheDocument()
  })

  it('erro de processamento: mostra o motivo do histórico e não oferece o resultado', async () => {
    sequencia = ['ERRO_PROCESSAMENTO']
    historico = [
      {
        evento_id: 'E1',
        documento_id: 'DOC-CLIN-2026-8942',
        tipo_evento: 'ERRO_PROCESSAMENTO',
        criado_em: '2026-10-21T10:47:00+00:00',
        ator: 'X',
        status_novo: 'ERRO_PROCESSAMENTO',
        motivo: 'Gemini indisponível',
        versao_esquema: '2.0.0',
      },
    ]
    await abrir()

    expect(screen.getByText('ERRO NO PROCESSAMENTO')).toBeInTheDocument()
    expect(screen.getByText('A triagem não foi concluída')).toBeInTheDocument()
    expect(screen.getByText('Gemini indisponível')).toBeInTheDocument()
    expect(screen.getByText('Falhou')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Ver resultado' })).not.toBeInTheDocument()
  })

  it('erro de persistência: explica e ainda permite ver o resultado', async () => {
    sequencia = ['ERRO_PERSISTENCIA']
    await abrir()

    expect(screen.getByText(/resultado não pôde ser salvo/)).toBeInTheDocument()
    expect(botao('Ver resultado')).toBeInTheDocument()
  })

  it('documento inexistente: mostra a mensagem e não oferece nova tentativa', async () => {
    sequencia = [404]
    await abrir()

    expect(screen.getByRole('alert')).toHaveTextContent(/Documento não encontrado/)
    expect(screen.queryByRole('button', { name: 'Tentar novamente' })).not.toBeInTheDocument()
  })

  it('falha de rede repetida mostra erro e "Tentar novamente" retoma', async () => {
    sequencia = ['REDE', 'REDE', 'REDE', 'PROCESSADO']
    await abrir()
    await avancar(INTERVALO_POLLING_MS * 3)

    expect(screen.getByRole('alert')).toHaveTextContent(/Não foi possível conectar à API/)

    fireEvent.click(botao('Tentar novamente'))
    await avancar(0)

    expect(screen.queryByText('Não foi possível acompanhar a triagem')).not.toBeInTheDocument()
    expect(screen.getByText('PROCESSADO')).toBeInTheDocument()
  })

  it('mostra no card Envio os dados vindos do formulário e o aviso de saída', async () => {
    await abrir({ formato: 'PDF', canal: 'Ambulatório', enviadoEm: '2026-10-21T13:47:00.000Z' })

    expect(screen.getByText('Formato').nextElementSibling).toHaveTextContent('PDF')
    expect(screen.getByText('Canal').nextElementSibling).toHaveTextContent('Ambulatório')
    expect(screen.getByText('Resposta').nextElementSibling).toHaveTextContent('202 Accepted')
    expect(screen.getByRole('heading', { name: 'Pode sair desta tela' })).toBeInTheDocument()
  })

  it('sem dados do formulário (acesso direto) o card Envio mostra "—"', async () => {
    await abrir()

    expect(screen.getByText('Formato').nextElementSibling).toHaveTextContent('—')
    expect(screen.getByText('Resposta').nextElementSibling).toHaveTextContent('—')
  })

  it('"Voltar" e "Simular de novo" levam à Nova triagem', async () => {
    await abrir()
    fireEvent.click(screen.getByRole('link', { name: 'Nova triagem' }))
    expect(screen.getByText('Tela Nova triagem')).toBeInTheDocument()
  })

  it('"Simular de novo" volta para a Nova triagem', async () => {
    await abrir()
    fireEvent.click(botao('Simular de novo'))
    expect(screen.getByText('Tela Nova triagem')).toBeInTheDocument()
  })

  it('"Ver resultado" abre a página de resultado do documento', async () => {
    await abrir()
    fireEvent.click(botao('Ver resultado'))
    expect(screen.getByText('Tela Resultado')).toBeInTheDocument()
  })
})
