import { describe, expect, it } from 'vitest'
import { ApiError } from '../services/api'
import { mensagemDeErro } from './mensagensErro'

describe('mensagemDeErro', () => {
  it('traduz códigos conhecidos da API', () => {
    expect(mensagemDeErro(new ApiError(413, 'ARQUIVO_MAIOR_QUE_LIMITE', 'Regra A6'))).toBe(
      'O arquivo excede o limite de 10 MB.',
    )
    expect(mensagemDeErro(new ApiError(415, 'FORMATO_NAO_SUPORTADO', 'x'))).toMatch(/Formato não suportado/)
  })

  it('explica quando o documento não existe (404)', () => {
    expect(mensagemDeErro(new ApiError(404, 'DOCUMENTO_NAO_ENCONTRADO', "Documento 'X' não encontrado."))).toMatch(
      /Documento não encontrado/,
    )
  })

  it('explica o conflito de ID de documento (409)', () => {
    expect(mensagemDeErro(new ApiError(409, 'DOCUMENTO_ID_CONFLITANTE', 'x'))).toBe(
      'Este ID já foi usado para outro documento. Deixe o campo vazio para gerar um novo ID ou informe outro.',
    )
  })

  it('repassa a mensagem da API em erros 400/422 sem código mapeado', () => {
    expect(mensagemDeErro(new ApiError(422, 'CAMPOS_INVALIDOS', 'Arquivo vazio (0 bytes).'))).toBe(
      'Arquivo vazio (0 bytes).',
    )
  })

  it('usa mensagem genérica para erro 5xx', () => {
    expect(mensagemDeErro(new ApiError(500, 'ERRO_INTERNO', 'detalhe interno'))).toMatch(/Erro interno/)
  })

  it('mantém a mensagem de falha de rede', () => {
    expect(mensagemDeErro(new ApiError(0, 'REDE', 'Sem conexão'))).toBe('Sem conexão')
  })

  it('trata erros desconhecidos', () => {
    expect(mensagemDeErro(new Error('x'))).toMatch(/erro inesperado/)
  })
})
