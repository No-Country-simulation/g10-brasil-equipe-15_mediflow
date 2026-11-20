import { afterEach, describe, expect, it, vi } from 'vitest'
import { CENARIOS_DEMO } from '../../fixtures'
import { carregarCaso, CASOS_TESTE } from './casosTeste'
import { escolherCenario } from '../../services/apiSimulada'

afterEach(() => vi.unstubAllGlobals())

describe('caso de revisão com ausência real', () => {
  it('envia imagem JPEG e alinha o simulador à idade ausente', async () => {
    const caso = CASOS_TESTE.find((item) => item.id === 'ambiguo')!
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('imagem')))
    const conteudo = await carregarCaso(caso)
    expect(conteudo.tipo).toBe('arquivo')
    if (conteudo.tipo !== 'arquivo') throw new Error('Imagem esperada')
    expect(conteudo.arquivo.name).toBe('Ausencia_Paciente_Idade.jpg')
    expect(conteudo.arquivo.type).toBe('image/jpeg')
    expect(escolherCenario(conteudo.arquivo.name, '')).toBe('ambiguo')
    expect(CENARIOS_DEMO.ambiguo.dados_extraidos?.paciente.idade).toBeNull()
    expect(CENARIOS_DEMO.ambiguo.qualidade?.campos_ausentes).toContain('paciente.idade')
    expect(CENARIOS_DEMO.ambiguo.decisao_roteamento?.destinos).toEqual(['FILA_REVISAO_HUMANA'])
  })
})
