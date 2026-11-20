import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { CENARIOS_DEMO } from '../../fixtures'
import { CardExames, CardMedicamentos } from './CardsDados'

describe('incerteza e ausência no resultado', () => {
  it('sinaliza a dose ilegível na própria linha do medicamento', () => {
    const triagem = structuredClone(CENARIOS_DEMO.ambiguo)
    triagem.dados_extraidos!.medicamentos = [{ nome: 'Nitroprussiato de sódio', dosagem: null }]
    triagem.qualidade!.campos_incertos = ['medicamentos[0].dosagem']
    render(<CardMedicamentos triagem={triagem} />)
    expect(screen.getByText('incerta ou ilegível')).toBeInTheDocument()
    expect(screen.getByText('Dose incerta ou ilegível')).toBeInTheDocument()
    expect(screen.getAllByRole('cell')[1]).toHaveTextContent('incerta ou ilegível')
  })

  it('campo crítico nulo não afirma que nenhum achado existe', () => {
    const triagem = structuredClone(CENARIOS_DEMO.urgente)
    triagem.dados_extraidos!.achados_criticos = null
    triagem.dados_extraidos!.inconsistencias_detectadas = []
    render(<CardExames triagem={triagem} />)
    expect(screen.getByText('Campo de achados críticos não informado.')).toBeInTheDocument()
    expect(screen.queryByText('Nenhum achado crítico identificado.')).not.toBeInTheDocument()
  })
})
