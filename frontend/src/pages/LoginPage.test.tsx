import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { beforeEach, describe, expect, it } from 'vitest'
import App from '../App'
import { encerrarSessao, INATIVIDADE_MAX_MS, iniciarSessao, limparTentativas, MAX_TENTATIVAS } from '../lib/sessao'

function abrir(rota: string) {
  const user = userEvent.setup()
  render(
    <MemoryRouter initialEntries={[rota]}>
      <App />
    </MemoryRouter>,
  )
  return user
}

async function preencher(user: ReturnType<typeof userEvent.setup>, crm: string, uf: string, senha: string) {
  if (crm) await user.type(screen.getByLabelText('CRM'), crm)
  if (uf) await user.selectOptions(screen.getByLabelText('UF'), uf)
  if (senha) await user.type(screen.getByLabelText('Senha'), senha)
  await user.click(screen.getByRole('button', { name: 'Entrar' }))
}

describe('login de demonstração', () => {
  beforeEach(() => {
    encerrarSessao()
    localStorage.clear()
    limparTentativas()
  })

  it('00a: sem sessão, qualquer tela leva ao login com os textos do Figma', () => {
    abrir('/triagens')

    expect(screen.getByRole('heading', { name: 'Entrar' })).toBeInTheDocument()
    expect(screen.getByText('Triagem clínica com IA, cada documento no lugar certo.')).toBeInTheDocument()
    expect(screen.getByText('Hackathon ONE G10 · Equipe 15')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Somente números')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Digite sua senha')).toBeInTheDocument()
    expect(screen.getByText('Conta de demonstração')).toBeInTheDocument()
    expect(screen.getByText(/CRM 145892 \/ SP · Dra. Renata Silveira/)).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Principal' })).not.toBeInTheDocument()
  })

  it('credenciais certas entram e voltam para a tela pedida', async () => {
    const user = abrir('/triagens?fila=revisao')

    await preencher(user, '145892', 'SP', 'mediflow')

    expect(await screen.findByRole('heading', { name: 'Triagens e filas' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Fila de revisão humana' })).toBeInTheDocument()
    expect(screen.getByText('Dra. Renata Silveira')).toBeInTheDocument()
  })

  it('00b: credenciais erradas mostram o aviso, bordas de erro e a nota de bloqueio', async () => {
    const user = abrir('/nova-triagem')

    await preencher(user, '145892', 'SP', 'errada')

    expect(screen.getByRole('alert')).toHaveTextContent('CRM, UF ou senha incorretos. Confira os dados e tente novamente.')
    expect(screen.getByLabelText('CRM')).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByLabelText('Senha')).toHaveClass('border-status-danger-fg')
    expect(screen.getByText('Após 5 tentativas incorretas o acesso fica bloqueado por 15 minutos.')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Entrar' })).toBeInTheDocument()
  })

  it('campos vazios contam como credencial inválida', async () => {
    const user = abrir('/nova-triagem')
    await preencher(user, '', '', '')
    expect(screen.getByRole('alert')).toHaveTextContent('CRM, UF ou senha incorretos')
  })

  it(`na ${MAX_TENTATIVAS}ª tentativa errada bloqueia, inclusive a senha certa`, async () => {
    const user = abrir('/nova-triagem')
    for (let i = 0; i < MAX_TENTATIVAS; i++) {
      await user.clear(screen.getByLabelText('Senha'))
      await preencher(user, i === 0 ? '145892' : '', i === 0 ? 'SP' : '', 'errada')
    }
    expect(screen.getByRole('alert')).toHaveTextContent(/Acesso bloqueado por excesso de tentativas/)

    await user.clear(screen.getByLabelText('Senha'))
    await preencher(user, '', '', 'mediflow')
    expect(screen.getByRole('alert')).toHaveTextContent(/Acesso bloqueado/)
  })

  it('00c: sessão vencida por inatividade leva ao login com o aviso azul', () => {
    iniciarSessao(false, Date.now() - INATIVIDADE_MAX_MS - 1000)
    abrir('/nova-triagem')

    expect(screen.getByRole('status')).toHaveTextContent('Sua sessão expirou por inatividade. Entre novamente para continuar.')
  })

  it('mostrar senha alterna o tipo do campo', async () => {
    const user = abrir('/login')
    const senha = screen.getByLabelText('Senha')
    expect(senha).toHaveAttribute('type', 'password')

    await user.click(screen.getByRole('button', { name: 'Mostrar senha' }))
    expect(senha).toHaveAttribute('type', 'text')
    expect(screen.getByRole('button', { name: 'Ocultar senha' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('"Esqueci minha senha" explica que é ambiente de demonstração', async () => {
    const user = abrir('/login')
    await user.click(screen.getByRole('button', { name: 'Esqueci minha senha' }))
    expect(screen.getByRole('status')).toHaveTextContent('Ambiente de demonstração: use a conta indicada abaixo.')
  })

  it('"Manter conectado" guarda a sessão no localStorage', async () => {
    const user = abrir('/login')
    await user.click(screen.getByLabelText('Manter conectado'))
    await preencher(user, '145892', 'SP', 'mediflow')

    expect(await screen.findByRole('heading', { name: 'Nova triagem' })).toBeInTheDocument()
    expect(localStorage.getItem('mediflow:sessao')).not.toBeNull()
  })

  it('com sessão ativa, /login vai direto para a Nova triagem', () => {
    iniciarSessao(false)
    abrir('/login')
    expect(screen.getByRole('heading', { name: 'Nova triagem' })).toBeInTheDocument()
  })

  it('"Sair da conta" encerra a sessão e volta ao login', async () => {
    iniciarSessao(false)
    const user = abrir('/nova-triagem')

    await user.click(screen.getByRole('button', { name: 'Sair da conta' }))

    expect(screen.getByRole('heading', { name: 'Entrar' })).toBeInTheDocument()
    expect(sessionStorage.getItem('mediflow:sessao')).toBeNull()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})
