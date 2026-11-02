import { useId, useState } from 'react'
import type { FormEvent } from 'react'
import { PageHeader } from '../components/layout'
import { CANAIS_ORIGEM } from '../components/triagem/canais'
import { Dropzone } from '../components/triagem/Dropzone'
import { ResultadoEnvio } from '../components/triagem/ResultadoEnvio'
import { TextoClinicoInput } from '../components/triagem/TextoClinicoInput'
import type { CanalOrigem } from '../components/triagem/canais'
import { Button, Field, Input, SegmentedControl, Select } from '../components/ui'
import { useSubmeterTriagem } from '../hooks/useSubmeterTriagem'

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
  const idCanal = useId()
  const idDocumento = useId()
  const [tipo, setTipo] = useState<TipoEnvio>('arquivo')
  const [canal, setCanal] = useState<CanalOrigem>(CANAIS_ORIGEM[0])
  const [documentoId, setDocumentoId] = useState('')
  const [arquivo, setArquivo] = useState<File | null>(null)
  const [texto, setTexto] = useState('')

  const { estado, submeter, reiniciar } = useSubmeterTriagem()

  const enviando = estado.fase === 'enviando'
  const temConteudo = tipo === 'arquivo' ? arquivo !== null : texto.trim().length > 0
  const podeEnviar = temConteudo && !enviando

  async function aoEnviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (!podeEnviar) return
    const aceito =
      tipo === 'arquivo' && arquivo
        ? await submeter({ tipo, arquivo, canalOrigem: canal, documentoId })
        : await submeter({ tipo: 'texto', texto, canalOrigem: canal, documentoId })

    // Limpa o formulário para evitar reenvio acidental do mesmo documento.
    if (aceito) {
      setArquivo(null)
      setTexto('')
      setDocumentoId('')
    }
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

      <div className="flex items-start gap-6">
        <form
          className="flex min-w-0 flex-1 flex-col gap-6 rounded-lg border border-border bg-surface p-7"
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
            <Dropzone arquivo={arquivo} onArquivoChange={editar(setArquivo)} />
          ) : (
            <TextoClinicoInput value={texto} onChange={editar(setTexto)} />
          )}

          <div className="flex gap-4">
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

          <div className="flex items-center gap-3 border-t border-border-subtle pt-5">
            <Button type="submit" disabled={!podeEnviar}>
              {enviando ? 'Enviando…' : 'Enviar para triagem'}
            </Button>
            <p className="m-0 text-caption text-text-placeholder">{podeEnviar ? AJUDA_PRONTO : AJUDA_SEM_CONTEUDO[tipo]}</p>
          </div>

          <ResultadoEnvio estado={estado} />
        </form>
      </div>
    </>
  )
}
