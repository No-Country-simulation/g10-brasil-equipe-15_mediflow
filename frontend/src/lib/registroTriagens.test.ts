import { beforeEach, describe, expect, it } from 'vitest'
import { CHAVE_REGISTRO, esquecerEnvios, lerRegistro, MAX_REGISTROS, registrarEnvio } from './registroTriagens'

const envio = (id: string) => ({ documentoId: id, canal: 'Ambulatório', enviadoEm: '2026-10-21T13:49:00.000Z' })

describe('registroTriagens', () => {
  beforeEach(() => localStorage.clear())

  it('guarda o mais recente primeiro e não duplica o mesmo ID', () => {
    registrarEnvio(envio('A'))
    registrarEnvio(envio('B'))
    registrarEnvio(envio('A'))
    expect(lerRegistro().map((e) => e.documentoId)).toEqual(['A', 'B'])
  })

  it(`mantém no máximo ${MAX_REGISTROS} envios`, () => {
    for (let i = 0; i < MAX_REGISTROS + 5; i++) registrarEnvio(envio(`D${i}`))
    expect(lerRegistro()).toHaveLength(MAX_REGISTROS)
    expect(lerRegistro()[0].documentoId).toBe(`D${MAX_REGISTROS + 4}`)
  })

  it('esquece IDs desconhecidos', () => {
    registrarEnvio(envio('A'))
    registrarEnvio(envio('B'))
    esquecerEnvios(['A'])
    expect(lerRegistro().map((e) => e.documentoId)).toEqual(['B'])
  })

  it('ignora conteúdo corrompido ou fora do formato', () => {
    localStorage.setItem(CHAVE_REGISTRO, '{quebrado')
    expect(lerRegistro()).toEqual([])
    localStorage.setItem(CHAVE_REGISTRO, JSON.stringify([envio('OK'), { documentoId: 1 }, null]))
    expect(lerRegistro().map((e) => e.documentoId)).toEqual(['OK'])
  })
})
