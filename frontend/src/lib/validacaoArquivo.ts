/** Regras de formato e tamanho espelhando src/ingestion/loader.py (a API faz a validação final). */

export const EXTENSOES_ACEITAS = ['.pdf', '.jpg', '.jpeg', '.png', '.webp', '.txt'] as const

/** 10 MB; o backend rejeita apenas arquivos acima desse valor. */
export const LIMITE_BYTES = 10 * 1024 * 1024

export const ACCEPT_INPUT = EXTENSOES_ACEITAS.join(',')

export function formatarTamanho(bytes: number): string {
  const formato = (valor: number) => valor.toLocaleString('pt-BR', { maximumFractionDigits: 1 })
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${formato(bytes / 1024)} KB`
  return `${formato(bytes / (1024 * 1024))} MB`
}

function extensaoDe(nome: string): string {
  const ponto = nome.lastIndexOf('.')
  return ponto === -1 ? '' : nome.slice(ponto).toLowerCase()
}

/** Devolve a mensagem de erro em português, ou `null` se o arquivo for válido. */
export function validarArquivo(arquivo: Pick<File, 'name' | 'size'>): string | null {
  if (!(EXTENSOES_ACEITAS as readonly string[]).includes(extensaoDe(arquivo.name))) {
    return 'Formato não suportado. Envie PDF, JPG, PNG, WEBP ou TXT.'
  }
  if (arquivo.size === 0) {
    return 'O arquivo está vazio (0 bytes).'
  }
  if (arquivo.size > LIMITE_BYTES) {
    // Arredonda para cima para nunca exibir "10 MB excede 10 MB".
    const mb = Math.ceil((arquivo.size / (1024 * 1024)) * 10) / 10
    return `O arquivo tem ${mb.toLocaleString('pt-BR')} MB e excede o limite de 10 MB.`
  }
  return null
}
