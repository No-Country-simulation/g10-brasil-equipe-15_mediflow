import { normalizarTriagem } from '../lib/normalizarTriagem'
import type { TriagemMediFlow } from '../types/clinical'
import cenario1 from './cenarios/cenario_1_rotina.json'
import cenario2 from './cenarios/cenario_2_urgencia_tep.json'
import cenario3 from './cenarios/cenario_3_ambiguidade_rasura.json'
import ambiguo from './expected/ambiguo.json'
import rotina from './expected/rotina.json'
import urgente from './expected/urgente.json'

export type IdCenario = 'rotina' | 'urgente' | 'ambiguo'

/**
 * Os 3 cenários da demo (JSONs da colega, formato anterior), já convertidos para o contrato atual.
 * Servem de resposta pronta para as telas de Processamento e Resultado.
 */
export const CENARIOS_DEMO: Readonly<Record<IdCenario, TriagemMediFlow>> = {
  rotina: normalizarTriagem(cenario1),
  urgente: normalizarTriagem(cenario2),
  ambiguo: normalizarTriagem(cenario3),
}

/** `resposta_esperada` dos fixtures de entrada de cada cenário (já no contrato atual). */
export const RESPOSTAS_ESPERADAS: Readonly<Record<IdCenario, TriagemMediFlow>> = {
  rotina: normalizarTriagem(rotina.resposta_esperada),
  urgente: normalizarTriagem(urgente.resposta_esperada),
  ambiguo: normalizarTriagem(ambiguo.resposta_esperada),
}
