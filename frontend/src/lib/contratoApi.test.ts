import { describe, expect, it } from 'vitest'
import respostaUrgenteSemOci from '../fixtures/api/resposta_urgente_sem_oci.json'
import { normalizarTriagem } from './normalizarTriagem'
import { rotuloStatusBackup } from './rotulos'

describe('contrato da API: resposta real urgente sem OCI', () => {
  const triagem = normalizarTriagem(respostaUrgenteSemOci)

  it('mantém status, destinos e notificação do roteamento', () => {
    expect(triagem.status).toBe('EM_REVISAO')
    expect(triagem.decisao_roteamento?.destinos).toEqual(['FILA_URGENCIA_MEDICA', 'FILA_REVISAO_HUMANA'])
    expect(triagem.decisao_roteamento?.notificacao?.gerada).toBe(true)
  })

  it('expõe o status de backup e o rótulo exibido ao usuário', () => {
    expect(triagem.armazenamento_oci?.status_backup).toBe('ignorado_ou_falha')
    expect(rotuloStatusBackup(triagem.armazenamento_oci?.status_backup)).toMatch(/^Não gravado no OCI/)
  })
})
