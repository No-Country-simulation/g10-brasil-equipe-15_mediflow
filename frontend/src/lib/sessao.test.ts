import { beforeEach, describe, expect, it } from 'vitest'
import {
  BLOQUEIO_MS,
  bloqueadoAte,
  credenciaisValidas,
  encerrarSessao,
  INATIVIDADE_MAX_MS,
  iniciarSessao,
  lerSessao,
  limparTentativas,
  MAX_TENTATIVAS,
  registrarFalha,
  tocarSessao,
} from './sessao'

describe('credenciaisValidas (login fake)', () => {
  it('aceita só a conta de demonstração', () => {
    expect(credenciaisValidas({ crm: '145892', uf: 'SP', senha: 'mediflow' })).toBe(true)
  })

  it('ignora pontuação no CRM, caixa na UF e espaços na senha', () => {
    expect(credenciaisValidas({ crm: '145.892', uf: 'sp', senha: ' mediflow ' })).toBe(true)
  })

  it.each([
    { crm: '145893', uf: 'SP', senha: 'mediflow' },
    { crm: '145892', uf: 'RJ', senha: 'mediflow' },
    { crm: '145892', uf: 'SP', senha: 'errada' },
    { crm: '', uf: '', senha: '' },
  ])('recusa %j', (c) => {
    expect(credenciaisValidas(c)).toBe(false)
  })
})

describe('sessão', () => {
  beforeEach(() => {
    encerrarSessao()
    localStorage.clear()
  })

  it('sem "manter conectado" fica no sessionStorage com o médico da conta demo', () => {
    iniciarSessao(false, 1000)
    expect(sessionStorage.getItem('mediflow:sessao')).not.toBeNull()
    expect(localStorage.getItem('mediflow:sessao')).toBeNull()
    expect(lerSessao(1000)).toMatchObject({
      tipo: 'ativa',
      sessao: { medico: { nome: 'Dra. Renata Silveira', crm: { numero: '145892', uf: 'SP' } } },
    })
  })

  it('com "manter conectado" fica no localStorage', () => {
    iniciarSessao(true, 1000)
    expect(localStorage.getItem('mediflow:sessao')).not.toBeNull()
    expect(sessionStorage.getItem('mediflow:sessao')).toBeNull()
  })

  it('expira após 30 min sem atividade e é apagada', () => {
    iniciarSessao(false, 0)
    expect(lerSessao(INATIVIDADE_MAX_MS).tipo).toBe('ativa')
    expect(lerSessao(INATIVIDADE_MAX_MS + 1).tipo).toBe('expirada')
    expect(lerSessao(INATIVIDADE_MAX_MS + 2).tipo).toBe('nenhuma')
  })

  it('a atividade adia a expiração', () => {
    iniciarSessao(false, 0)
    tocarSessao(INATIVIDADE_MAX_MS - 1)
    expect(lerSessao(INATIVIDADE_MAX_MS * 2 - 2).tipo).toBe('ativa')
  })

  it('"manter conectado" não expira por inatividade', () => {
    iniciarSessao(true, 0)
    expect(lerSessao(INATIVIDADE_MAX_MS * 100).tipo).toBe('ativa')
  })

  it('encerrar apaga dos dois storages; conteúdo corrompido conta como sem sessão', () => {
    iniciarSessao(true)
    encerrarSessao()
    expect(lerSessao().tipo).toBe('nenhuma')
    sessionStorage.setItem('mediflow:sessao', '{quebrado')
    expect(lerSessao().tipo).toBe('nenhuma')
  })
})

describe('tentativas e bloqueio', () => {
  beforeEach(() => {
    localStorage.clear()
    limparTentativas()
  })

  it(`bloqueia por 15 min na ${MAX_TENTATIVAS}ª falha`, () => {
    for (let i = 1; i < MAX_TENTATIVAS; i++) expect(registrarFalha(0).bloqueadoAte).toBeNull()
    expect(registrarFalha(0).bloqueadoAte).toBe(BLOQUEIO_MS)
    expect(bloqueadoAte(BLOQUEIO_MS - 1)).toBe(BLOQUEIO_MS)
  })

  it('o bloqueio vence e a contagem recomeça', () => {
    for (let i = 0; i < MAX_TENTATIVAS; i++) registrarFalha(0)
    expect(bloqueadoAte(BLOQUEIO_MS)).toBeNull()
    expect(registrarFalha(BLOQUEIO_MS).falhas).toBe(1)
  })
})
