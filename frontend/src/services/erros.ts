/** Erro de chamada à API. `codigo` segue o envelope da API (ou REDE / RESPOSTA_INVALIDA). */
export class ApiError extends Error {
  readonly status: number
  readonly codigo: string
  readonly detalhes?: unknown

  constructor(status: number, codigo: string, mensagem: string, detalhes?: unknown) {
    super(mensagem)
    this.name = 'ApiError'
    this.status = status
    this.codigo = codigo
    this.detalhes = detalhes
  }
}
