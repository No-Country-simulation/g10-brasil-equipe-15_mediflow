import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import cenarioAmbiguo from '../fixtures/cenarios/cenario_3_ambiguidade_rasura.json'
import rotina from '../fixtures/expected/rotina.json'
import urgente from '../fixtures/expected/urgente.json'
import urgenteRevisao from '../fixtures/expected/urgente_revisao.json'
import { registrarEnvio } from '../lib/registroTriagens'
import { ListaTriagensPage } from './ListaTriagensPage'

function json(status: number, corpo: unknown) {
  return new Response(JSON.stringify(corpo), { status, headers: { 'Content-Type': 'application/json' } })
}

/** Respostas de GET /triagens/{id} por ID; `null` = ainda em andamento. */
const RESULTADOS: Record<string, unknown> = {
  'DOC-ROT': rotina.resposta_esperada,
  // Dra. Renata Silveira, CRM 145892/SP: aparece em "Meus documentos".
  'DOC-URG': urgente.resposta_esperada,
  'DOC-SIM': urgenteRevisao.resposta_esperada,
  'DOC-AMB': cenarioAmbiguo,
  'DOC-AND': null,
}

function Local() {
  const { pathname, search } = useLocation()
  return <p data-testid="local">{pathname + search}</p>
}

describe('ListaTriagensPage', () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    localStorage.clear()
    for (const id of Object.keys(RESULTADOS).reverse()) {
      registrarEnvio({ documentoId: id, canal: 'Ambulatório', enviadoEm: new Date().toISOString() })
    }
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
    fetchMock.mockImplementation(async (url: string) => {
      const id = url.split('/triagens/')[1].split('/')[0]
      const resultado = RESULTADOS[id] as { status: string } | null
      if (url.endsWith('/status')) {
        const status = resultado ? resultado.status : 'PROCESSANDO'
        return json(200, { documento_id: id, status, destinos: [], requer_auditoria_humana: false, concluido: Boolean(resultado) })
      }
      return json(200, resultado)
    })
  })

  async function abrir(rota: string, variante: 'triagens' | 'meus' = 'triagens') {
    const user = userEvent.setup()
    render(
      <MemoryRouter initialEntries={[rota]}>
        <Routes>
          <Route path="/triagens" element={<><ListaTriagensPage variante={variante} /><Local /></>} />
          <Route path="/meus-documentos" element={<ListaTriagensPage variante="meus" />} />
          <Route path="*" element={<Local />} />
        </Routes>
      </MemoryRouter>,
    )
    await screen.findByText(/documentos?$/, { selector: 'span' })
    await screen.findByRole('table').catch(() => null)
    return user
  }

  const linhas = () => within(screen.getByRole('table')).getAllByRole('row').slice(1)
  const card = (rotulo: string) => screen.getByRole('button', { name: new RegExp(`^${rotulo}: \\d+$`) })

  it('04a: todas as triagens, contagens das filas e colunas do Figma', async () => {
    await abrir('/triagens')

    expect(screen.getByRole('heading', { name: 'Triagens e filas' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Todas as triagens' })).toBeInTheDocument()
    expect(screen.getByText('· 5 documentos')).toBeInTheDocument()
    expect(card('Todos')).toHaveAttribute('aria-pressed', 'true')
    expect(card('Todos')).toHaveTextContent('5')
    expect(card('Fila de urgência')).toHaveTextContent('2')
    expect(card('Fila de revisão')).toHaveTextContent('2')
    expect(card('Processados')).toHaveTextContent('2')
    expect(card('Em andamento')).toHaveTextContent('1')
    expect(card('Com erro')).toHaveTextContent('0')
    expect(screen.getAllByRole('columnheader').map((c) => c.textContent)).toEqual([
      'Documento', 'Tipo', 'Prioridade', 'Status', 'Destino(s)', 'Score', 'Recebido', 'Ação',
    ])
    expect(linhas()).toHaveLength(5)
    expect(screen.getByRole('link', { name: 'Nova triagem' })).toHaveAttribute('href', '/nova-triagem')
  })

  it('linha concluída mostra tipo, badges, destinos e score com aviso de limiar', async () => {
    await abrir('/triagens')

    const amb = linhas().find((l) => l.textContent?.includes('DOC-AMB')) as HTMLElement
    expect(amb).toHaveTextContent('Receituário médico')
    expect(within(amb).getByText('EM_REVISAO')).toBeInTheDocument()
    expect(within(amb).getByText('Revisão humana')).toBeInTheDocument()
    expect(within(amb).getByText('abaixo de 0,85')).toBeInTheDocument()

    const sim = linhas().find((l) => l.textContent?.includes('DOC-SIM')) as HTMLElement
    expect(within(sim).getByText('Urgência médica')).toBeInTheDocument()
    expect(within(sim).getByText('Revisão humana')).toBeInTheDocument()

    const and = linhas().find((l) => l.textContent?.includes('DOC-AND')) as HTMLElement
    expect(within(and).getByText('PROCESSANDO')).toBeInTheDocument()
  })

  it('04b: fila de revisão pela URL, com a faixa de aviso', async () => {
    await abrir('/triagens?fila=revisao')

    expect(screen.getByRole('heading', { name: 'Fila de revisão humana' })).toBeInTheDocument()
    expect(card('Fila de revisão')).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText(/Fila lógica de revisão/)).toBeInTheDocument()
    expect(linhas().map((l) => l.textContent?.match(/DOC-(ROT|URG|SIM|AMB|AND)/)?.[0])).toEqual(['DOC-SIM', 'DOC-AMB'])
  })

  it('clicar num card troca a fila e grava na URL', async () => {
    const user = await abrir('/triagens')

    await user.click(card('Fila de urgência'))

    expect(screen.getByTestId('local')).toHaveTextContent('/triagens?fila=urgencia')
    expect(screen.getByRole('heading', { name: 'Fila de urgência médica' })).toBeInTheDocument()
    expect(screen.queryByText(/Fila lógica de revisão/)).not.toBeInTheDocument()
    expect(linhas()).toHaveLength(2)
  })

  it('busca por ID e mostra estado de busca sem resultado', async () => {
    const user = await abrir('/triagens')

    await user.type(screen.getByLabelText('Buscar ID'), 'amb')
    expect(linhas()).toHaveLength(1)
    expect(screen.getByText('· 1 documento')).toBeInTheDocument()

    await user.clear(screen.getByLabelText('Buscar ID'))
    await user.type(screen.getByLabelText('Buscar ID'), 'nada')
    expect(screen.getByText('Nenhum documento com esse ID.')).toBeInTheDocument()
  })

  it('fila vazia tem mensagem própria', async () => {
    await abrir('/triagens?fila=erro')
    expect(screen.getByText('Nenhum documento nesta fila.')).toBeInTheDocument()
  })

  it('"Abrir" leva ao resultado quando concluída e ao processamento quando não', async () => {
    const user = await abrir('/triagens')

    await user.click(screen.getByRole('button', { name: 'Abrir DOC-ROT' }))
    expect(screen.getByTestId('local')).toHaveTextContent('/resultado/DOC-ROT')
  })

  it('"Abrir" numa triagem em andamento vai ao processamento', async () => {
    const user = await abrir('/triagens')

    await user.click(screen.getByRole('button', { name: 'Abrir DOC-AND' }))
    expect(screen.getByTestId('local')).toHaveTextContent('/nova-triagem/processamento/DOC-AND')
  })

  it('04c: meus documentos mostra só os do CRM da médica logada (145892/SP)', async () => {
    render(
      <MemoryRouter initialEntries={['/meus-documentos']}>
        <Routes>
          <Route path="/meus-documentos" element={<ListaTriagensPage variante="meus" />} />
        </Routes>
      </MemoryRouter>,
    )
    await screen.findByText('· 2 documentos')

    expect(screen.getAllByRole('heading', { name: 'Meus documentos' })).toHaveLength(2)
    expect(screen.getByText('Filtro por CRM aplicado só neste navegador, sobre os dados da demo. A API não restringe o acesso.')).toBeInTheDocument()
    expect(screen.getByText('Dra. Renata Silveira')).toBeInTheDocument()
    // DOC-URG e DOC-SIM são da Dra. Renata; rotina e ambíguo são de outros médicos.
    expect(card('Meus documentos')).toHaveTextContent('2')
    expect(card('Urgentes')).toHaveTextContent('2')
    expect(card('Em revisão')).toHaveTextContent('1')
    expect(linhas().map((l) => l.textContent?.match(/DOC-(ROT|URG|SIM|AMB|AND)/)?.[0])).toEqual(['DOC-URG', 'DOC-SIM'])
  })

  it('sem nenhum envio registrado convida a enviar uma triagem', async () => {
    localStorage.clear()
    render(
      <MemoryRouter initialEntries={['/triagens']}>
        <ListaTriagensPage variante="triagens" />
      </MemoryRouter>,
    )

    expect(await screen.findByText(/Nenhuma triagem enviada neste navegador ainda/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Enviar uma triagem' })).toHaveAttribute('href', '/nova-triagem')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('API fora do ar: mostra o erro e "Tentar novamente"', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))
    const user = userEvent.setup()
    render(
      <MemoryRouter initialEntries={['/triagens']}>
        <ListaTriagensPage variante="triagens" />
      </MemoryRouter>,
    )

    expect(await screen.findByRole('alert')).toHaveTextContent(/Não foi possível conectar à API/)
    fetchMock.mockReset()
    fetchMock.mockResolvedValue(json(404, { codigo: 'DOCUMENTO_NAO_ENCONTRADO', mensagem: 'x' }))
    await user.click(screen.getByRole('button', { name: 'Tentar novamente' }))
    expect(await screen.findByText(/Nenhuma triagem enviada neste navegador ainda/)).toBeInTheDocument()
  })
})
