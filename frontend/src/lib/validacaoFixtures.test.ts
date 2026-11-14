import { describe, expect, it } from 'vitest'
import docx from '../fixtures/erros/Validacao_ArquivoDocx.json'
import grande from '../fixtures/erros/Validacao_ArquivoGrande.json'
import mimeInvalido from '../fixtures/erros/Validacao_MimeInvalido.json'
import vazio from '../fixtures/erros/Validacao_ArquivoVazio.json'
import zip from '../fixtures/erros/Validacao_ArquivoZip.json'
import { ApiError } from '../services/api'
import { mensagemDeErro } from './mensagensErro'
import { LIMITE_BYTES, validarArquivo } from './validacaoArquivo'

/**
 * Casos de `tests/fixtures/catalogo` (blocos Validacao e Limite). Usamos o nome e o tamanho reais
 * de cada arquivo, porque `validarArquivo` só lê esses dois campos. Os arquivos grandes não estão
 * no git (são recriados pelo gerador), então aqui o tamanho é fabricado.
 */

type Envelope = { resposta_esperada: { http: number; codigo_funcional: string; mensagem: string } }

function erroDaApi({ resposta_esperada: r }: Envelope): ApiError {
  return new ApiError(r.http, r.codigo_funcional, r.mensagem)
}

const MB = 1024 * 1024

describe('fixtures do bloco Limite que o navegador deve aceitar', () => {
  it.each([
    ['Limite_Formato_Png.png', 128_014],
    ['Limite_Formato_Webp.webp', 63_500],
    ['Limite_Tamanho_10MB.pdf', LIMITE_BYTES],
    ['Limite_Tamanho_10MB.jpg', 158_523],
    ['Limite_Tamanho_10MB.txt', 1_353],
  ])('aceita %s', (name, size) => {
    expect(validarArquivo({ name, size })).toBeNull()
  })

  it('10 MB exatos passam mesmo com o conteúdo de um arquivo real', () => {
    const arquivo = new File([new Uint8Array(LIMITE_BYTES)], 'Limite_Tamanho_10MB.pdf')
    expect(arquivo.size).toBe(LIMITE_BYTES)
    expect(validarArquivo(arquivo)).toBeNull()
  })
})

describe('fixtures do bloco Limite acima de 10 MB', () => {
  it.each(['Limite_Tamanho_Acima10MB.pdf', 'Limite_Texto_Acima10MB.txt'])('barra %s (10,5 MB)', (name) => {
    expect(validarArquivo({ name, size: 10.5 * MB })).toMatch(/10,5 MB e excede o limite de 10 MB/)
  })

  it('barra Validacao_ArquivoGrande.pdf (25 MB), como a API (413)', () => {
    expect(grande.resposta_esperada.http).toBe(413)
    expect(validarArquivo({ name: 'Validacao_ArquivoGrande.pdf', size: 25 * MB })).toMatch(
      /25 MB e excede o limite de 10 MB/,
    )
    expect(mensagemDeErro(erroDaApi(grande))).toBe('O arquivo excede o limite de 10 MB.')
  })
})

describe('fixtures do bloco Validacao', () => {
  it('Validacao_ArquivoDocx.docx: o navegador barra com a mesma mensagem da API (415)', () => {
    const doNavegador = validarArquivo({ name: 'Validacao_ArquivoDocx.docx', size: 922 })
    expect(doNavegador).toMatch(/Formato não suportado/)
    expect(doNavegador).toBe(mensagemDeErro(erroDaApi(docx)))
  })

  it('Validacao_ArquivoZip.zip: o navegador barra com a mesma mensagem da API (415)', () => {
    const doNavegador = validarArquivo({ name: 'Validacao_ArquivoZip.zip', size: 170 })
    expect(doNavegador).toMatch(/Formato não suportado/)
    expect(doNavegador).toBe(mensagemDeErro(erroDaApi(zip)))
  })

  it('Validacao_ArquivoVazio.pdf: o navegador barra e a API também (422)', () => {
    expect(vazio.resposta_esperada.http).toBe(422)
    expect(validarArquivo({ name: 'Validacao_ArquivoVazio.pdf', size: 0 })).toMatch(/vazio/)
    // 422 não tem texto próprio no front: a mensagem da API é exibida.
    expect(mensagemDeErro(erroDaApi(vazio))).toMatch(/0 bytes/)
  })

  it('Validacao_MimeInvalido.pdf: só a API detecta (extensão .pdf com conteúdo PNG)', () => {
    expect(validarArquivo({ name: 'Validacao_MimeInvalido.pdf', size: 7_729 })).toBeNull()
    expect(mensagemDeErro(erroDaApi(mimeInvalido))).toMatch(/não corresponde à extensão/)
  })
})
