export type CasoTeste = {
  id: 'rotina' | 'urgente' | 'ambiguo'
  titulo: string
  tag: string
  descricao: string
  esperado: string
  /** Arquivo em public/samples (cópia de data/samples na raiz do repositório). */
  arquivo: string
}

/** Os três cenários da demonstração (textos do Figma). */
export const CASOS_TESTE: readonly CasoTeste[] = [
  {
    id: 'rotina',
    titulo: 'Fluxo padrão',
    tag: 'ROTINA',
    descricao: 'Laudo laboratorial sem sinais de urgência.',
    esperado: 'Prontuário eletrônico',
    arquivo: '01_laudo_rotina.pdf',
  },
  {
    id: 'urgente',
    titulo: 'Caso urgente',
    tag: 'URGENTE',
    descricao: 'Laudo de tomografia com TEP agudo.',
    esperado: 'Fila de urgência + alerta',
    arquivo: '02_laudo_urgencia_tep.pdf',
  },
  {
    id: 'ambiguo',
    titulo: 'Caso ambíguo',
    tag: 'REVISÃO',
    descricao: 'Receita sem idade, CRM rasurado e dose suspeita.',
    esperado: 'Fila de revisão humana',
    arquivo: '03_receituario_ambiguo.pdf',
  },
]

/** Baixa o PDF de exemplo e o devolve como `File`, pronto para o formulário. */
export async function carregarArquivoDoCaso(caso: CasoTeste): Promise<File> {
  const resposta = await fetch(`${import.meta.env.BASE_URL}samples/${caso.arquivo}`)
  if (!resposta.ok) {
    throw new Error(`Não foi possível carregar o exemplo "${caso.titulo}".`)
  }
  const blob = await resposta.blob()
  return new File([blob], caso.arquivo, { type: 'application/pdf' })
}
