import { useId, useState } from 'react'
import { PageHeader } from '../components/layout'
import { CANAIS_ORIGEM } from '../components/triagem/canais'
import type { CanalOrigem } from '../components/triagem/canais'
import { Button, Field, Input, SegmentedControl, Select } from '../components/ui'

type TipoEnvio = 'arquivo' | 'texto'

const OPCOES_TIPO = [
  { value: 'arquivo', label: 'Arquivo' },
  { value: 'texto', label: 'Texto' },
] as const

const AJUDA_SEM_CONTEUDO: Record<TipoEnvio, string> = {
  arquivo: 'Selecione um arquivo para enviar.',
  texto: 'Cole o texto para enviar.',
}

export function NovaTriagemPage() {
  const idCanal = useId()
  const idDocumento = useId()
  const [tipo, setTipo] = useState<TipoEnvio>('arquivo')
  const [canal, setCanal] = useState<CanalOrigem>(CANAIS_ORIGEM[0])
  const [documentoId, setDocumentoId] = useState('')

  return (
    <>
      <PageHeader
        title="Nova triagem"
        subtitle="Envie um documento clínico ou cole o texto. O MediFlow classifica, extrai os dados e decide o destino."
      />

      <div className="flex items-start gap-6">
        <form
          className="flex min-w-0 flex-1 flex-col gap-6 rounded-lg border border-border bg-surface p-7"
          onSubmit={(evento) => evento.preventDefault()}
        >
          <div>
            <SegmentedControl
              aria-label="Tipo de envio"
              options={OPCOES_TIPO}
              value={tipo}
              onChange={setTipo}
            />
          </div>

          {/* Conteúdo da aba: dropzone (commit 10) e campo de texto (commit 11). */}
          <div className="flex min-h-55 items-center justify-center rounded-lg border-2 border-dashed border-border-dashed bg-subtle text-sm text-text-placeholder">
            {tipo === 'arquivo' ? 'Área de envio de arquivo em construção' : 'Campo de texto em construção'}
          </div>

          <div className="flex gap-4">
            <Field label="Canal de origem" htmlFor={idCanal}>
              <Select
                id={idCanal}
                value={canal}
                onChange={(evento) => setCanal(evento.target.value as CanalOrigem)}
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
                onChange={(evento) => setDocumentoId(evento.target.value)}
                autoComplete="off"
              />
            </Field>
          </div>

          <div className="flex items-center gap-3 border-t border-border-subtle pt-5">
            <Button type="submit" disabled>
              Enviar para triagem
            </Button>
            <p className="m-0 text-caption text-text-placeholder">{AJUDA_SEM_CONTEUDO[tipo]}</p>
          </div>
        </form>
      </div>
    </>
  )
}
