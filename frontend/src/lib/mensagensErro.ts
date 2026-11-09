import { ApiError } from '../services/api'

const POR_CODIGO: Record<string, string> = {
  FORMATO_NAO_SUPORTADO: 'Formato não suportado. Envie PDF, JPG, PNG, WEBP ou TXT.',
  MIME_INVALIDO: 'O conteúdo do arquivo não corresponde à extensão. Verifique se o arquivo não está corrompido.',
  ARQUIVO_MAIOR_QUE_LIMITE: 'O arquivo excede o limite de 10 MB.',
  PDF_PROTEGIDO: 'PDF protegido por senha não pode ser processado.',
  PDF_CORROMPIDO: 'O PDF está corrompido ou truncado.',
  DOCUMENTO_NAO_ENCONTRADO: 'Documento não encontrado. Confira o ID ou envie uma nova triagem.',
  DOCUMENTO_ID_CONFLITANTE:
    'Este ID já foi usado para outro documento. Deixe o campo vazio para gerar um novo ID ou informe outro.',
}

/** Texto amigável para exibir ao usuário a partir de um erro da API ou de rede. */
export function mensagemDeErro(erro: unknown): string {
  if (!(erro instanceof ApiError)) {
    return 'Ocorreu um erro inesperado. Tente novamente.'
  }
  if (erro.codigo === 'REDE') return erro.message
  if (POR_CODIGO[erro.codigo]) return POR_CODIGO[erro.codigo]
  if (erro.status >= 500) return 'Erro interno do servidor. Tente novamente em instantes.'
  // 400 e 422 (ex.: arquivo vazio, PDF com mais de 20 páginas): a API já devolve a mensagem em português.
  return erro.message
}
