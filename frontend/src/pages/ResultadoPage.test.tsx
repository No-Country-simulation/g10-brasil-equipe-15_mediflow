import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { CENARIOS_DEMO } from '../fixtures'
import cenarioUrgente from '../fixtures/cenarios/cenario_2_urgencia_tep.json'
import cenarioAmbiguo from '../fixtures/cenarios/cenario_3_ambiguidade_rasura.json'
import conflitoDose from '../fixtures/expected/conflito_dose.json'
import rotina from '../fixtures/expected/rotina.json'
import urgenteRevisao from '../fixtures/expected/urgente_revisao.json'
import { SessaoProvider } from '../components/sessao'
import { registrarEnvio } from '../lib/registroTriagens'
import { encerrarSessao, iniciarSessao } from '../lib/sessao'
import { ResultadoPage } from './ResultadoPage'

function json(status: number, corpo: unknown) {
  return new Response(JSON.stringify(corpo), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

const TERMINAIS = ['PROCESSADO', 'EM_REVISAO', 'ERRO_PROCESSAMENTO', 'ERRO_PERSISTENCIA']

const historicoPadrao = [
  {
    evento_id: 'E1',
    documento_id: 'DOC-1',
    tipo_evento: 'RECEBIDO',
    criado_em: '2026-10-21T13:49:02.000Z',
    ator: 'API',
    status_anterior: null,
    status_novo: 'RECEBIDO',
    motivo: 'Requisição aceita (202)',
    versao_esquema: '2.0.0',
  },
  {
    evento_id: 'E2',
    documento_id: 'DOC-1',
    tipo_evento: 'ROTEADO',
    criado_em: '2026-10-21T13:49:10.000Z',
    ator: 'LANGGRAPH_ROUTER',
    status_anterior: 'PROCESSANDO',
    status_novo: 'PROCESSADO',
    motivo: 'Encaminhado ao prontuário',
    versao_esquema: '2.0.0',
  },
]

describe('ResultadoPage', () => {
  const fetchMock = vi.fn()
  /** Resposta de GET /triagens/{id}; o status de /status sai dela. */
  let triagem: Record<string, unknown>
  let statusForcado: string | null
  let falhaStatus: 404 | 'REDE' | null
  let reprocessoOk: boolean
  let historico: unknown[]

  beforeEach(() => {
    localStorage.clear()
    encerrarSessao()
    iniciarSessao(false)
    // Enviado por este navegador: o acesso restrito (00d) não se aplica.
    registrarEnvio({
      documentoId: 'DOC-1',
      canal: 'Ambulatório',
      enviadoEm: new Date().toISOString(),
    })
    triagem = {
      ...rotina.resposta_esperada,
      canal_origem: 'Ambulatório',
      versao_esquema: '2.0.0',
    }
    statusForcado = null
    falhaStatus = null
    reprocessoOk = true
    historico = historicoPadrao
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
    fetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
      if (url.endsWith('/status')) {
        if (falhaStatus === 404)
          return json(404, {
            codigo: 'DOCUMENTO_NAO_ENCONTRADO',
            mensagem: 'x',
          })
        if (falhaStatus === 'REDE') throw new TypeError('Failed to fetch')
        const status = statusForcado ?? (triagem.status as string)
        return json(200, {
          documento_id: 'DOC-1',
          status,
          destinos: [],
          requer_auditoria_humana: false,
          concluido: TERMINAIS.includes(status),
        })
      }
      if (url.endsWith('/historico')) return json(200, historico)
      if (url.endsWith('/reprocessar-persistencia') && init?.method === 'POST') {
        if (!reprocessoOk)
          return json(502, {
            codigo: 'ERRO_PERSISTENCIA',
            mensagem: 'Falha na retentativa OCI',
          })
        triagem = { ...triagem, status: 'PROCESSADO', erro: null }
        return json(200, triagem)
      }
      return json(200, triagem)
    })
  })

  async function abrir() {
    const user = userEvent.setup()
    render(
      <SessaoProvider>
        <MemoryRouter initialEntries={['/resultado/DOC-1']}>
          <Routes>
            <Route path="/resultado/:documentoId" element={<ResultadoPage />} />
            <Route path="/nova-triagem" element={<p>Tela Nova triagem</p>} />
            <Route path="/nova-triagem/processamento/:documentoId" element={<p>Tela Processamento</p>} />
            <Route path="/meus-documentos" element={<p>Tela Meus documentos</p>} />
            <Route path="/login" element={<p>Tela Login</p>} />
          </Routes>
        </MemoryRouter>
      </SessaoProvider>,
    )
    await screen.findByText(
      /Resultado da triagem|ainda está em processamento|Não foi possível carregar|Acesso restrito/,
    )
    return user
  }

  const card = (titulo: string) => screen.getByRole('heading', { name: titulo }).closest('section') as HTMLElement

  it('03a rotina: cabeçalho, banner de sucesso, cards e histórico', async () => {
    await abrir()

    expect(screen.getByRole('heading', { name: 'Resultado da triagem' })).toBeInTheDocument()
    expect(screen.getByText('PROCESSADO')).toBeInTheDocument()
    expect(screen.getByText(/^Recebido 21\/10\/2026 \d{2}:\d{2} · Ambulatório · esquema v2\.0\.0$/)).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Processado · encaminhado automaticamente')
    expect(within(card('Classificação')).getByText('Laudo de exame de imagem')).toBeInTheDocument()
    expect(within(card('Classificação')).getByText('Rotina')).toBeInTheDocument()
    expect(within(card('Medicamentos')).getByText('Nenhum medicamento identificado no documento.')).toBeInTheDocument()
    expect(within(card('Decisão de roteamento')).getByText('PRONTUARIO_ELETRONICO')).toBeInTheDocument()
    expect(within(card('Decisão de roteamento')).getByText('Nenhum alerta gerado')).toBeInTheDocument()
    expect(within(card('Confiança')).getByText('Score atingiu o limiar 0,85')).toBeInTheDocument()
    expect(within(card('Histórico')).getAllByRole('listitem')).toHaveLength(2)
    expect(within(card('Histórico')).getByText('PROCESSANDO → PROCESSADO')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Triagens e filas' })).toHaveAttribute('href', '/triagens')
  })

  it('03b urgente: banner vermelho com o alerta simulado e o CID do TEP', async () => {
    triagem = cenarioUrgente
    await abrir()

    const banner = screen.getByRole('alert')
    expect(banner).toHaveTextContent('Urgente · encaminhado à fila de urgência médica')
    expect(banner).toHaveTextContent('Alerta registrado como evento simulado (SIMULADO_SLACK_PLANTAO)')
    expect(within(card('Dados extraídos')).getByText('I26.9')).toBeInTheDocument()
    expect(within(card('Classificação')).getByText('Urgente')).toBeInTheDocument()
    expect(within(card('Exames e urgência')).getByText('ANGIOTOMOGRAFIA DE TÓRAX')).toBeInTheDocument()
    expect(within(card('Exames e urgência')).getByText('Sim — urgência detectada')).toBeInTheDocument()
    expect(
      within(card('Decisão de roteamento')).getByText('Evento simulado registrado (SIMULADO_SLACK_PLANTAO)'),
    ).toBeInTheDocument()
  })

  it('urgente sem alerta registrado: a linha Alerta mostra a falha e o encaminhamento mantido', async () => {
    triagem = {
      ...CENARIOS_DEMO.urgente,
      decisao_roteamento: { ...CENARIOS_DEMO.urgente.decisao_roteamento, notificacao: null },
    }
    await abrir()

    expect(within(card('Decisão de roteamento')).getByText(/^Falha ao registrar o evento de alerta simulado\./)).toHaveTextContent(
      'O encaminhamento à fila de urgência foi mantido.',
    )
    expect(screen.getByRole('alert')).toHaveTextContent('Falha ao registrar o evento de alerta simulado')
  })

  it('histórico é exibido em ordem cronológica mesmo se a API devolver fora de ordem', async () => {
    historico = [...historicoPadrao].reverse()
    await abrir()

    const tipos = within(card('Histórico')).getAllByRole('listitem').map((li) => li.textContent)
    expect(tipos[0]).toContain('RECEBIDO')
    expect(tipos[1]).toContain('ROTEADO')
  })

  it('03c urgente + revisão: dois banners e dois destinos', async () => {
    triagem = urgenteRevisao.resposta_esperada
    await abrir()

    expect(screen.getByText('EM_REVISAO')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('Urgente')
    expect(screen.getByText('Em revisão · encaminhado à fila de revisão humana')).toBeInTheDocument()
    const roteamento = card('Decisão de roteamento')
    expect(within(roteamento).getByText('FILA_URGENCIA_MEDICA')).toBeInTheDocument()
    expect(within(roteamento).getByText('FILA_REVISAO_HUMANA')).toBeInTheDocument()
    expect(within(roteamento).getByText('Sim')).toBeInTheDocument()
  })

  it('score acima do limiar com revisão obrigatória: card neutro e encaminhamento segue a API', async () => {
    const base = urgenteRevisao.resposta_esperada
    triagem = {
      ...base,
      classificacao: { ...base.classificacao, score_classificacao: 0.95 },
      qualidade: { ...base.qualidade, score_extracao: 0.92, score_combinado: 0.92 },
      decisao_roteamento: {
        ...base.decisao_roteamento,
        justificativa_roteamento: 'Urgência: revisão humana obrigatória pela regra de negócio.',
      },
    }
    await abrir()

    const confianca = card('Confiança')
    expect(within(confianca).getByText('Score atingiu o limiar 0,85')).toBeInTheDocument()
    expect(within(confianca).queryByText(/fluxo automático/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/fluxo automático permitido/i)).not.toBeInTheDocument()
    const roteamento = card('Decisão de roteamento')
    expect(within(roteamento).getByText('FILA_REVISAO_HUMANA')).toBeInTheDocument()
    expect(within(roteamento).getByText('Sim')).toBeInTheDocument()
    expect(screen.getByText('Em revisão · encaminhado à fila de revisão humana')).toBeInTheDocument()
  })

  it('03d ambíguo: campos ausentes com tag, score abaixo do limiar e motivos da revisão', async () => {
    triagem = cenarioAmbiguo
    await abrir()

    const dados = card('Dados extraídos')
    expect(within(dados).getAllByText('Ausente · exige revisão')).toHaveLength(2)
    expect(within(dados).getByText('Ausente · não exige revisão')).toBeInTheDocument()
    expect(within(dados).getAllByText('obrigatório')).toHaveLength(5)
    expect(
      screen.getByText('Médico solicitante não consta no documento', {
        exact: false,
      }),
    ).toBeInTheDocument()
    expect(within(card('Confiança')).getByText('Abaixo do limiar 0,85 — exige revisão humana')).toBeInTheDocument()
  })

  it('tabela de medicamentos marca a dose suspeita e o conflito aparece no card', async () => {
    triagem = conflitoDose.resposta_esperada
    await abrir()

    const tabela = within(card('Medicamentos')).getByRole('table')
    const linha = within(tabela).getAllByRole('row')[1]
    expect(linha).toHaveTextContent('Losartana potássica')
    expect(within(linha).getByText('500 mg')).toHaveClass('bg-status-warning-bg')
    expect(within(linha).getByText('Dose suspeita')).toBeInTheDocument()
    expect(within(card('Conflitos')).getByText('DOSE_SUSPEITA')).toBeInTheDocument()
    expect(within(card('Conflitos')).getByText('Gravidade alta')).toBeInTheDocument()
  })

  it('03e erro de persistência: só cabeçalho, alerta e histórico; "Tentar salvar de novo" recarrega', async () => {
    triagem = {
      ...triagem,
      status: 'ERRO_PERSISTENCIA',
      erro: { codigo: 'ERRO_PERSISTENCIA', mensagem: 'Timeout' },
    }
    const user = await abrir()

    expect(screen.getByText('ERRO_PERSISTENCIA')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('Triagem não confirmada · falha ao salvar o resultado')
    expect(screen.queryByRole('heading', { name: 'Classificação' })).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Histórico' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Tentar salvar de novo' }))

    expect(await screen.findByText('PROCESSADO')).toBeInTheDocument()
    expect(
      fetchMock.mock.calls.some(([u, i]) => String(u).endsWith('/reprocessar-persistencia') && i?.method === 'POST'),
    ).toBe(true)
    expect(screen.getByRole('heading', { name: 'Classificação' })).toBeInTheDocument()
  })

  it('falha ao reprocessar mostra a mensagem e mantém o alerta', async () => {
    triagem = { ...triagem, status: 'ERRO_PERSISTENCIA' }
    reprocessoOk = false
    const user = await abrir()

    await user.click(screen.getByRole('button', { name: 'Tentar salvar de novo' }))

    expect(await screen.findByText(/Erro interno do servidor|Falha na retentativa OCI/)).toBeInTheDocument()
    expect(screen.getByText('ERRO_PERSISTENCIA')).toBeInTheDocument()
  })

  it('erro de processamento: sem "Tentar salvar"; "Reenviar documento" volta à Nova triagem', async () => {
    triagem = { ...triagem, status: 'ERRO_PROCESSAMENTO' }
    const user = await abrir()

    expect(screen.getByRole('alert')).toHaveTextContent('Triagem não concluída · falha no processamento')
    expect(screen.queryByRole('button', { name: 'Tentar salvar de novo' })).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Reenviar documento' }))
    expect(screen.getByText('Tela Nova triagem')).toBeInTheDocument()
  })

  it('triagem ainda em andamento: não pede o resultado e leva ao processamento', async () => {
    statusForcado = 'PROCESSANDO'
    const user = await abrir()

    expect(screen.getByText('A triagem ainda está em processamento')).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([u]) => String(u).endsWith('/triagens/DOC-1'))).toBe(false)

    await user.click(screen.getByRole('link', { name: 'Acompanhar o processamento' }))
    expect(screen.getByText('Tela Processamento')).toBeInTheDocument()
  })

  it('documento inexistente: mensagem sem botão de nova tentativa', async () => {
    falhaStatus = 404
    await abrir()

    expect(screen.getByRole('alert')).toHaveTextContent(/Documento não encontrado/)
    expect(screen.queryByRole('button', { name: 'Tentar novamente' })).not.toBeInTheDocument()
  })

  it('falha de rede: "Tentar novamente" recarrega', async () => {
    falhaStatus = 'REDE'
    const user = await abrir()
    expect(screen.getByRole('alert')).toHaveTextContent(/Não foi possível conectar à API/)

    falhaStatus = null
    await user.click(screen.getByRole('button', { name: 'Tentar novamente' }))

    expect(await screen.findByText('PROCESSADO')).toBeInTheDocument()
  })

  it('"Ver JSON da resposta" mostra a resposta da API como veio', async () => {
    triagem = cenarioAmbiguo
    const user = await abrir()

    const botao = screen.getByRole('button', { name: 'Ver JSON da resposta' })
    expect(botao).toHaveAttribute('aria-expanded', 'false')
    await user.click(botao)

    const painel = screen.getByRole('region', { name: 'JSON da resposta' })
    // O JSON é o bruto da API (formato anterior), não o normalizado.
    expect(painel).toHaveTextContent('"medico_solicitante"')
    await user.click(screen.getByRole('button', { name: 'Ocultar JSON da resposta' }))
    expect(screen.queryByRole('region', { name: 'JSON da resposta' })).not.toBeInTheDocument()
  })

  describe('acesso restrito (00d)', () => {
    beforeEach(() => {
      // Documento de outro médico (CRM 165432/SP) que NÃO foi enviado por este navegador.
      localStorage.clear()
    })

    it('mostra a 00d com o documento, o CRM do solicitante e o da sessão', async () => {
      await abrir()

      expect(screen.getByRole('heading', { name: 'Acesso restrito' })).toBeInTheDocument()
      expect(screen.getByText('Solicitante do documento').nextElementSibling).toHaveTextContent('CRM 165432 / SP')
      expect(screen.getByText('Você está logada como').nextElementSibling).toHaveTextContent('CRM 145892 / SP')
      expect(screen.queryByRole('heading', { name: 'Classificação' })).not.toBeInTheDocument()
    })

    it('"Voltar para meus documentos" e "Entrar com outra conta"', async () => {
      const user = await abrir()
      await user.click(screen.getByRole('button', { name: 'Voltar para meus documentos' }))
      expect(screen.getByText('Tela Meus documentos')).toBeInTheDocument()
    })

    it('"Entrar com outra conta" encerra a sessão e vai ao login', async () => {
      const user = await abrir()
      await user.click(screen.getByRole('button', { name: 'Entrar com outra conta' }))
      expect(screen.getByText('Tela Login')).toBeInTheDocument()
      expect(sessionStorage.getItem('mediflow:sessao')).toBeNull()
    })

    it('documento da própria médica abre normalmente mesmo sem ter sido enviado aqui', async () => {
      triagem = { ...urgenteRevisao.resposta_esperada }
      await abrir()
      expect(screen.getByRole('heading', { name: 'Resultado da triagem' })).toBeInTheDocument()
    })

    it('documento sem CRM extraído não é bloqueado', async () => {
      triagem = cenarioAmbiguo
      await abrir()
      expect(screen.getByRole('heading', { name: 'Resultado da triagem' })).toBeInTheDocument()
    })
  })
})
