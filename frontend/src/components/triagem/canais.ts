/**
 * Canais de origem exibidos no formulário. O Figma só mostra o valor "Pronto-socorro" e usa
 * "Ambulatório", "Internação" e "Recepção" nas listas de triagens; a API aceita qualquer texto.
 */
export const CANAIS_ORIGEM = ['Pronto-socorro', 'Ambulatório', 'Internação', 'Recepção'] as const

export type CanalOrigem = (typeof CANAIS_ORIGEM)[number]
