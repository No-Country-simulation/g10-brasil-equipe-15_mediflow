import { describe, expect, it } from 'vitest'
import { formatarDataHora, lerDadosEnvio, rotuloFormato } from './dadosEnvio'

describe('rotuloFormato', () => {
  it('usa "Texto" sem arquivo e a extensão em maiúsculas com arquivo', () => {
    expect(rotuloFormato(null)).toBe('Texto')
    expect(rotuloFormato({ name: 'laudo.final.pdf' })).toBe('PDF')
    expect(rotuloFormato({ name: 'foto.JPG' })).toBe('JPG')
    expect(rotuloFormato({ name: 'semextensao' })).toBe('Arquivo')
  })
})

describe('lerDadosEnvio', () => {
  it('aceita o formato esperado', () => {
    const dados = { formato: 'PDF', canal: 'Ambulatório', enviadoEm: '2026-10-21T10:47:00Z' }
    expect(lerDadosEnvio(dados)).toEqual(dados)
  })

  it.each([null, undefined, 'x', 42, {}, { formato: 'PDF' }, { formato: 1, canal: 'a', enviadoEm: 'b' }])(
    'devolve null para %j',
    (estado) => {
      expect(lerDadosEnvio(estado)).toBeNull()
    },
  )
})

describe('formatarDataHora', () => {
  it('formata dia/mês/ano e hora:minuto', () => {
    expect(formatarDataHora('2026-10-21T13:47:00.000Z')).toMatch(/^21\/10\/2026 \d{2}:\d{2}$/)
  })

  it('devolve "—" para vazio ou data inválida', () => {
    expect(formatarDataHora(null)).toBe('—')
    expect(formatarDataHora('')).toBe('—')
    expect(formatarDataHora('ontem')).toBe('—')
  })
})
