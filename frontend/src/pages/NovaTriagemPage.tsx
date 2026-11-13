import { useId, useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { PageHeader } from '../components/layout'
import { CANAIS_ORIGEM } from '../components/triagem/canais'
import { carregarCaso } from '../components/triagem/casosTeste'
import type { CasoTeste } from '../components/triagem/casosTeste'
import { CasosTestePanel } from '../components/triagem/CasosTestePanel'
import { Dropzone } from '../components/triagem/Dropzone'
import { ResultadoEnvio } from '../components/triagem/ResultadoEnvio'
import { TextoClinicoInput } from '../components/triagem/TextoClinicoInput'
import type { CanalOrigem } from '../components/triagem/canais'
import { Button, Field, Input, SegmentedControl, Select } from '../components/ui'
import { useSubmeterTriagem } from '../hooks/useSubmeterTriagem'
import { rotuloFormato } from '../lib/dadosEnvio'
import { registrarEnvio } from '../lib/registroTriagens'
import type { DadosEnvio } from '../lib/dadosEnvio'

type TipoEnvio = 'arquivo' | 'texto'

const OPCOES_TIPO = [
  { value: 'arquivo', label: 'Arquivo' },
  { value: 'texto', label: 'Texto' },
] as const

const AJUDA_SEM_CONTEUDO: Record<TipoEnvio, string> = {
  arquivo: 'Selecione um arquivo para enviar.',
  texto: 'Cole o texto para enviar.',
}

const AJUDA_PRONTO = 'Validação final de formato e tamanho também acontece na API.'

export function NovaTriagemPage() {
  const navigate = useNavigate()
  const idCanal = useId()
  const idDocumento = useId()
  const [tipo, setTipo] = useState<TipoEnvio>('arquivo')
  const [canal, setCanal] = useState<CanalOrigem>(CANAIS_ORIGEM[0])
  const [documentoId, setDocumentoId] = useState('')
  const [arquivo, setArquivo] = useState<File | null>(null)
  const [texto, setTexto] = useState('')

  const [casoId, setCasoId] = useState<CasoTeste['id'] | null>(null)
  const [carregandoCaso, setCarregandoCaso] = useState(false)
  const [erroCaso, setErroCaso] = useState<string | null>(null)
  const { estado, submeter, reiniciar } = useSubmeterTriagem()

  const enviando = estado.fase === 'enviando'
  const temConteudo = tipo === 'arquivo' ? arquivo !== null : texto.trim().length > 0
  const podeEnviar = temConteudo && !enviando

  async function aoEnviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (!podeEnviar) return
    const resposta =
      tipo === 'arquivo' && arquivo
        ? await submeter({ tipo, arquivo, canalOrigem: canal, documentoId })
        : await submeter({ tipo: 'texto', texto, canalOrigem: canal, documentoId })
    if (!resposta) return

    // Aceito (202): segue para o acompanhamento. O formulário é desmontado, então não precisa ser limpo.
    const envio: DadosEnvio = {
      formato: rotuloFormato(tipo === 'arquivo' ? arquivo : null),
      canal,
      enviadoEm: new Date().toISOString(),
    }
    // Base provisória da lista de "Triagens e filas" (a API ainda não lista triagens).
    registrarEnvio({ documentoId: resposta.documento_id, canal, enviadoEm: envio.enviadoEm })
    navigate(`/nova-triagem/processamento/${encodeURIComponent(resposta.documento_id)}`, { state: envio })
  }

  /** Carrega o documento do caso de teste no formulário, na aba Arquivo ou Texto conforme o caso. */
  async function selecionarCaso(caso: CasoTeste) {
    setErroCaso(null)
    setCarregandoCaso(true)
    try {
      const conteudo = await carregarCaso(caso)
      reiniciar()
      setTipo(conteudo.tipo)
      if (conteudo.tipo === 'arquivo') {
        setArquivo(conteudo.arquivo)
        setTexto('')
      } else {
        setTexto(conteudo.texto)
        setArquivo(null)
      }
      setCasoId(caso.id)
    } catch (erro) {
      setErroCaso(erro instanceof Error ? erro.message : 'Não foi possível carregar o exemplo.')
    } finally {
      setCarregandoCaso(false)
    }
  }

  /** Troca ou remove o arquivo manualmente: deixa de ser "um caso de teste carregado". */
  function trocarArquivo(novo: File | null) {
    reiniciar()
    setCasoId(null)
    setArquivo(novo)
  }

  /** Qualquer edição do formulário descarta o feedback do envio anterior. */
  function editar<T>(definir: (valor: T) => void) {
    return (valor: T) => {
      reiniciar()
      definir(valor)
    }
  }

  return (
    <>
      <PageHeader
        title="Nova triagem"
        subtitle="Envie um documento clínico ou cole o texto. O MediFlow classifica, extrai os dados e decide o destino."
      />

      {/* Abaixo de 1280px os casos de teste vão para baixo do formulário (fora do Figma, que é só desktop). */}
      <div className="flex flex-col gap-6 xl:flex-row xl:items-start">
        <form
          className="flex min-w-0 flex-1 flex-col gap-6 rounded-lg border border-border bg-surface p-4 sm:p-7"
          onSubmit={aoEnviar}
        >
          <div>
            <SegmentedControl
              aria-label="Tipo de envio"
              options={OPCOES_TIPO}
              value={tipo}
              onChange={editar(setTipo)}
            />
          </div>

          {tipo === 'arquivo' ? (
            <Dropzone arquivo={arquivo} onArquivoChange={trocarArquivo} />
          ) : (
            <TextoClinicoInput value={texto} onChange={editar(setTexto)} />
          )}

          <div className="flex flex-col gap-4 sm:flex-row">
            <Field label="Canal de origem" htmlFor={idCanal}>
              <Select
                id={idCanal}
                value={canal}
                onChange={(evento) => editar(setCanal)(evento.target.value as CanalOrigem)}
              >
                {CANAIS_ORIGEM.map((opcao) => (
                  <option key={opcao} value={opcao}>
                    {opcao}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="ID do documento" hint="(opcional)" htmlFor={idDocumento}>
              <Input
                id={idDocumento}
                placeholder="Gerado automaticamente"
                value={documentoId}
                onChange={(evento) => editar(setDocumentoId)(evento.target.value)}
                autoComplete="off"
              />
            </Field>
          </div>

          <div className="flex flex-wrap items-center gap-3 border-t border-border-subtle pt-5">
            {/* Durante o envio o botão fica aria-disabled, não disabled: assim o foco não se perde e,
                se o envio falhar, Enter reenvia dali mesmo. O aoEnviar já ignora o clique repetido. */}
            <Button type="submit" disabled={!temConteudo} aria-disabled={enviando || undefined}>
              {enviando ? 'Enviando…' : 'Enviar para triagem'}
            </Button>
            <p className="m-0 text-caption text-text-placeholder">{podeEnviar ? AJUDA_PRONTO : AJUDA_SEM_CONTEUDO[tipo]}</p>
          </div>

          <ResultadoEnvio estado={estado} />
        </form>

        <CasosTestePanel
          selecionadoId={casoId}
          carregando={carregandoCaso}
          erro={erroCaso}
          onSelecionar={selecionarCaso}
        />
      </div>
    </>
  )
}
