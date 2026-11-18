import { describe, expect, it } from 'vitest'
import { LIMITE_BYTES, formatarTamanho, validarArquivo } from './validacaoArquivo'

describe('validarArquivo', () => {
  it.each(['laudo.pdf', 'LAUDO.PDF', 'foto.jpg', 'foto.jpeg', 'scan.png', 'img.webp', 'nota.txt'])(
    'aceita %s',
    (name) => {
      expect(validarArquivo({ name, size: 100 })).toBeNull()
    },
  )

  it.each(['planilha.docx', 'script.exe', 'semextensao'])('rejeita formato de %s', (name) => {
    expect(validarArquivo({ name, size: 100 })).toMatch(/Formato não suportado/)
  })

  it('rejeita arquivo vazio', () => {
    expect(validarArquivo({ name: 'a.pdf', size: 0 })).toMatch(/vazio/)
  })

  it('aceita exatamente 10 MB e rejeita 1 byte acima', () => {
    expect(validarArquivo({ name: 'a.pdf', size: LIMITE_BYTES })).toBeNull()
    expect(validarArquivo({ name: 'a.pdf', size: LIMITE_BYTES + 1 })).toMatch(/excede o limite de 10 MB/)
  })

  it('não exibe "10 MB excede 10 MB" para um arquivo pouco acima do limite', () => {
    expect(validarArquivo({ name: 'a.pdf', size: LIMITE_BYTES + 1 })).toContain('10,1 MB')
  })
})

describe('formatarTamanho', () => {
  it('usa B, KB e MB', () => {
    expect(formatarTamanho(512)).toBe('512 B')
    expect(formatarTamanho(2048)).toBe('2 KB')
    expect(formatarTamanho(5 * 1024 * 1024)).toBe('5 MB')
  })
})
