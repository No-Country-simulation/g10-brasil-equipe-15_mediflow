import { ApiError } from '../services/api'

const POR_CODIGO: Record<string, string> = {
  FORMATO_NAO_SUPORTADO: 'Formato não suportado. Envie PDF, JPG, PNG, WEBP ou TXT.',
  MIME_INVALIDO: 'O conteúdo do arquivo não corresponde à extensão. Verifique se o arquivo não está corrompido.',
  PDF_PROTEGIDO: 'PDF protegido por senha não pode ser processado.',
  PDF_CORROMPIDO: 'O PDF está corrompido ou truncado.',
  DOCUMENTO_NAO_ENCONTRADO: 'Documento não encontrado. Confira o ID ou envie uma nova triagem.',
  DOCUMENTO_ID_CONFLITANTE:
    'Este ID já foi usado para outro documento. Deixe o campo vazio para gerar um novo ID ou informe outro.',
}

function mensagemLimiteExcedido(erro: ApiError): string {
  const detalhes =
    typeof erro.detalhes === 'object' && erro.detalhes !== null
      ? (erro.detalhes as Record<string, unknown>)
      : null

  if (detalhes?.motivo === 'PAGINAS_EXCEDIDAS') {
    const total = detalhes.total_paginas
    const limite = detalhes.limite_paginas
    if (typeof total === 'number' && typeof limite === 'number') {
      return `O PDF tem ${total} páginas e excede o limite de ${limite} páginas.`
    }
    return 'O PDF excede o limite de 20 páginas.'
  }

  if (detalhes?.motivo === 'TAMANHO_EXCEDIDO') {
    return 'O arquivo excede o limite de 10 MB.'
  }

  // Fallback defensivo para payloads/mocks sem o bloco estruturado `detalhes`.
  if (/p[áa]ginas?/i.test(erro.message)) {
    return 'O PDF excede o limite de 20 páginas.'
  }

  return 'O arquivo excede o limite de 10 MB.'
}

/** Texto amigável para exibir ao usuário a partir de um erro da API ou de rede. */
export function mensagemDeErro(erro: unknown): string {
  if (!(erro instanceof ApiError)) {
    return 'Ocorreu um erro inesperado. Tente novamente.'
  }
  if (erro.codigo === 'REDE') return erro.message
  if (erro.codigo === 'ARQUIVO_MAIOR_QUE_LIMITE') return mensagemLimiteExcedido(erro)
  if (POR_CODIGO[erro.codigo]) return POR_CODIGO[erro.codigo]
  if (erro.status >= 500) return 'Erro interno do servidor. Tente novamente em instantes.'
  // 400 e 422 sem código mapeado (ex.: arquivo vazio, campos inválidos): a API já devolve a mensagem em português.
  return erro.message
}
