import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AvisoSaidaDaTela, CardEnvio } from './index'

const envio = { formato: 'Texto', canal: 'Pronto-socorro', enviadoEm: '2026-10-21T13:47:00.000Z' }

describe('CardEnvio', () => {
  const writeText = vi.fn()

  beforeEach(() => {
    writeText.mockReset().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('mostra formato, canal, hora e resposta quando o envio foi feito nesta sessão', () => {
    render(<CardEnvio documentoId="DOC-1" envio={envio} enviadoEm={null} />)

    expect(screen.getByRole('heading', { name: 'Envio' })).toBeInTheDocument()
    expect(screen.getByText('Formato').nextElementSibling).toHaveTextContent('Texto')
    expect(screen.getByText('Canal').nextElementSibling).toHaveTextContent('Pronto-socorro')
    expect(screen.getByText('Enviado').nextElementSibling).toHaveTextContent(/^21\/10\/2026 \d{2}:\d{2}$/)
    expect(screen.getByText('Resposta').nextElementSibling).toHaveTextContent('202 Accepted')
  })

  it('em acesso direto pela URL mostra "—" no que não se sabe', () => {
    render(<CardEnvio documentoId="DOC-1" envio={null} enviadoEm={null} />)

    for (const rotulo of ['Formato', 'Canal', 'Enviado', 'Resposta']) {
      expect(screen.getByText(rotulo).nextElementSibling).toHaveTextContent('—')
    }
  })

  it('prefere a hora do histórico à do navegador e mostra a hora mesmo sem o estado do envio', () => {
    render(<CardEnvio documentoId="DOC-1" envio={null} enviadoEm="2026-10-22T15:05:00.000Z" />)

    expect(screen.getByText('Enviado').nextElementSibling).toHaveTextContent(/^22\/10\/2026 \d{2}:\d{2}$/)
  })

  it('copia o ID e confirma por 2 segundos', async () => {
    vi.useFakeTimers()
    render(<CardEnvio documentoId="DOC-CLIN-2026-8942" envio={envio} enviadoEm={null} />)

    fireEvent.click(screen.getByRole('button', { name: 'Copiar ID do documento' }))
    await act(() => vi.advanceTimersByTimeAsync(0))

    expect(writeText).toHaveBeenCalledWith('DOC-CLIN-2026-8942')
    expect(screen.getByRole('button', { name: 'ID copiado' })).toBeInTheDocument()

    await act(() => vi.advanceTimersByTimeAsync(2000))
    expect(screen.getByRole('button', { name: 'Copiar ID do documento' })).toBeInTheDocument()
  })

  it('avisa quando o navegador não deixa copiar', async () => {
    writeText.mockRejectedValue(new Error('negado'))
    render(<CardEnvio documentoId="DOC-1" envio={envio} enviadoEm={null} />)

    fireEvent.click(screen.getByRole('button', { name: 'Copiar ID do documento' }))

    await waitFor(() => expect(screen.getByRole('button', { name: 'Não foi possível copiar' })).toBeInTheDocument())
  })
})

describe('AvisoSaidaDaTela', () => {
  it('explica que a triagem continua e linka para Triagens e filas', () => {
    render(
      <MemoryRouter>
        <AvisoSaidaDaTela />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: 'Pode sair desta tela' })).toBeInTheDocument()
    expect(screen.getByText(/A triagem continua no servidor/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Triagens e filas' })).toHaveAttribute('href', '/triagens')
  })
})
