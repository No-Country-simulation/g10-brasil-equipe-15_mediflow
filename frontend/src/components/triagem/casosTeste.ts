import { CENARIOS_DEMO } from '../../fixtures'
import type { IdCenario } from '../../fixtures'
import { ROTULO_DESTINO } from '../../lib/rotulos'

export type CasoTeste = {
  id: IdCenario
  titulo: string
  tag: string
  descricao: string
  /** Destino que a triagem deve devolver, lido do cenário da demo. */
  esperado: string
  /** PDF em public/samples (cópia do fixture). */
  arquivo: string
  /** Se informado, o caso é carregado na aba Texto com o conteúdo deste arquivo (Figma 01b). */
  texto?: string
}

export type ConteudoDoCaso =
  | { tipo: 'arquivo'; arquivo: File }
  | { tipo: 'texto'; texto: string }


function esperadoDe(id: IdCenario): string {
  const roteamento = CENARIOS_DEMO[id].decisao_roteamento
  const destino = roteamento?.destino_principal
  const rotulo = destino ? ROTULO_DESTINO[destino] : 'Sem destino'
  return roteamento?.notificacao?.gerada ? `${rotulo} + alerta` : rotulo
}

/** Os três cenários da demonstração. Os documentos vêm dos fixtures de `tests/fixtures`. */
export const CASOS_TESTE: readonly CasoTeste[] = [
  {
    id: 'rotina',
    titulo: 'Fluxo padrão',
    tag: 'ROTINA',
    descricao: 'Laudo de ultrassonografia sem sinais de urgência.',
    esperado: esperadoDe('rotina'),
    arquivo: 'rotina/Matriz_LaudoDeImagem_Texto.pdf',
  },
  {
    id: 'urgente',
    titulo: 'Caso urgente',
    tag: 'URGENTE',
    descricao: 'Laudo de tomografia com TEP agudo, colado como texto.',
    esperado: esperadoDe('urgente'),
    arquivo: 'urgente/Matriz_LaudoDeImagem_Pdf.pdf',
    texto: 'urgente/Matriz_LaudoDeImagem_Pdf.txt',
  },
  {
    id: 'ambiguo',
    titulo: 'Caso ambíguo',
    tag: 'REVISÃO',
    descricao: 'Lombalgia com score 0,84, logo abaixo do limiar de 0,85.',
    esperado: esperadoDe('ambiguo'),
    arquivo: 'ambiguo/Borda_Score_084.pdf',
  },
]

async function baixar(caminho: string, titulo: string): Promise<Response> {
  const resposta = await fetch(`${import.meta.env.BASE_URL}samples/${caminho}`)
  if (!resposta.ok) {
    throw new Error(`Não foi possível carregar o exemplo "${titulo}".`)
  }
  return resposta
}

/** Baixa o documento do caso e o devolve pronto para o formulário (arquivo ou texto). */
export async function carregarCaso(caso: CasoTeste): Promise<ConteudoDoCaso> {
  if (caso.texto) {
    const resposta = await baixar(caso.texto, caso.titulo)
    return { tipo: 'texto', texto: await resposta.text() }
  }
  const resposta = await baixar(caso.arquivo, caso.titulo)
  const blob = await resposta.blob()
  const nome = caso.arquivo.split('/').pop() ?? caso.arquivo
  return { tipo: 'arquivo', arquivo: new File([blob], nome, { type: 'application/pdf' }) }
}
