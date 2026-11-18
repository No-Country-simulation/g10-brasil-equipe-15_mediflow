import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { derivarEtapas } from '../../lib/etapasProcessamento'
import { BarraProgresso, ListaEtapas } from './index'

describe('BarraProgresso', () => {
  it('mostra o rótulo, a porcentagem e expõe o progresso para leitores de tela', () => {
    render(<BarraProgresso porcentagem={50} rotulo="Consultando o status a cada 2 s" />)

    expect(screen.getByText('Consultando o status a cada 2 s')).toBeInTheDocument()
    expect(screen.getByText('50%')).toBeInTheDocument()
    const barra = screen.getByRole('progressbar', { name: 'Progresso da triagem' })
    expect(barra).toHaveAttribute('aria-valuenow', '50')
    expect(barra.firstElementChild).toHaveStyle({ width: '50%' })
  })

  it('limita valores fora de 0 a 100', () => {
    const { rerender } = render(<BarraProgresso porcentagem={140} rotulo="x" />)
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '100')
    rerender(<BarraProgresso porcentagem={-5} rotulo="x" />)
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '0')
  })
})

describe('ListaEtapas', () => {
  it('02a: 4 concluídas, a 5ª em andamento e as demais aguardando', () => {
    const { etapas } = derivarEtapas({ status: 'PROCESSANDO', etapaVisual: 5 })
    render(<ListaEtapas etapas={etapas} />)

    const itens = within(screen.getByRole('list', { name: 'Etapas da triagem' })).getAllByRole('listitem')
    expect(itens).toHaveLength(8)
    expect(within(itens[0]).getByText('Concluído')).toBeInTheDocument()
    expect(within(itens[4]).getByText('Extração e validação')).toBeInTheDocument()
    expect(within(itens[4]).getByText('Em andamento')).toBeInTheDocument()
    expect(within(itens[7]).getByText('Aguardando')).toBeInTheDocument()
    expect(screen.getAllByText('Concluído')).toHaveLength(4)
    expect(screen.getAllByText('Aguardando')).toHaveLength(3)
  })

  it('marca só a etapa em andamento com aria-current="step"', () => {
    const { etapas } = derivarEtapas({ status: 'PROCESSANDO', etapaVisual: 5 })
    render(<ListaEtapas etapas={etapas} />)

    const atual = screen.getAllByRole('listitem').filter((li) => li.getAttribute('aria-current') === 'step')
    expect(atual).toHaveLength(1)
    expect(atual[0]).toHaveTextContent('Extração e validação')
  })

  it('02b: tudo concluído, sem etapa atual', () => {
    const { etapas } = derivarEtapas({ status: 'PROCESSADO' })
    render(<ListaEtapas etapas={etapas} />)

    expect(screen.getAllByText('Concluído')).toHaveLength(8)
    expect(screen.queryByText('Em andamento')).not.toBeInTheDocument()
    expect(screen.getAllByRole('listitem').some((li) => li.hasAttribute('aria-current'))).toBe(false)
  })

  it('mostra "Falhou" com texto, não só com cor', () => {
    const { etapas } = derivarEtapas({ status: 'ERRO_PERSISTENCIA' })
    render(<ListaEtapas etapas={etapas} />)

    expect(within(screen.getAllByRole('listitem')[7]).getByText('Falhou')).toBeInTheDocument()
  })

  it('mostra o caminho do resultado em fonte mono quando existe', () => {
    const { etapas } = derivarEtapas({ status: 'PROCESSADO', caminhoResultado: 'processados/urgentes/DOC-1.json' })
    render(<ListaEtapas etapas={etapas} />)

    expect(screen.getByText('processados/urgentes/DOC-1.json')).toHaveClass('font-mono')
  })

  it('esconde os marcadores dos leitores de tela', () => {
    const { etapas } = derivarEtapas({ status: 'PROCESSADO' })
    const { container } = render(<ListaEtapas etapas={etapas} />)

    expect(container.querySelectorAll('li > span[aria-hidden="true"]')).toHaveLength(8)
  })
})
