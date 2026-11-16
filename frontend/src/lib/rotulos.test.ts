import { describe, expect, it } from 'vitest'
import { rotuloStatusBackup } from './rotulos'

describe('rotuloStatusBackup', () => {
  it('traduz os status conhecidos ignorando maiúsculas', () => {
    expect(rotuloStatusBackup('sucesso')).toBe('Salvo')
    expect(rotuloStatusBackup('IGNORADO_OU_FALHA')).toBe(
      'Não gravado no OCI (ambiente sem armazenamento configurado)',
    )
    expect(rotuloStatusBackup('falha')).toBe('Falha ao gravar')
    expect(rotuloStatusBackup('pendente')).toBe('Gravação pendente')
  })

  it('usa traço para vazio e devolve status desconhecido como veio', () => {
    expect(rotuloStatusBackup(null)).toBe('—')
    expect(rotuloStatusBackup('')).toBe('—')
    expect(rotuloStatusBackup('novo_status')).toBe('novo_status')
  })
})
