import { useRef, useState } from 'react'
import type { DragEvent } from 'react'
import { cx } from '../../lib/cx'
import { ACCEPT_INPUT, formatarTamanho, validarArquivo } from '../../lib/validacaoArquivo'
import { Button, Icon } from '../ui'

type DropzoneProps = {
  arquivo: File | null
  /** Chamado com o arquivo válido, ou `null` ao remover. Arquivos inválidos nunca chegam aqui. */
  onArquivoChange: (arquivo: File | null) => void
}

const NOTA = 'PDF, JPG, PNG, WEBP ou TXT · até 10 MB · até 20 páginas'

export function Dropzone({ arquivo, onArquivoChange }: DropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [arrastando, setArrastando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  function abrirSeletor() {
    inputRef.current?.click()
  }

  function receber(arquivos: FileList | null) {
    if (!arquivos || arquivos.length === 0) return
    if (arquivos.length > 1) {
      setErro('Envie um arquivo por vez.')
      return
    }
    const candidato = arquivos[0]
    const mensagem = validarArquivo(candidato)
    setErro(mensagem)
    if (!mensagem) onArquivoChange(candidato)
  }

  function remover() {
    setErro(null)
    onArquivoChange(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  function aoArrastar(evento: DragEvent<HTMLDivElement>, ativo: boolean) {
    evento.preventDefault()
    // Ignora o "leave" disparado ao passar sobre elementos filhos.
    if (!ativo && evento.currentTarget.contains(evento.relatedTarget as Node | null)) return
    setArrastando(ativo)
  }

  function aoSoltar(evento: DragEvent<HTMLDivElement>) {
    evento.preventDefault()
    setArrastando(false)
    receber(evento.dataTransfer.files)
  }

  return (
    <div className="flex flex-col gap-2">
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT_INPUT}
        className="sr-only"
        tabIndex={-1}
        aria-label="Selecionar arquivo"
        onChange={(evento) => {
          receber(evento.target.files)
          // Permite escolher o mesmo arquivo de novo após um erro ou remoção.
          evento.target.value = ''
        }}
      />

      <div
        onDragEnter={(evento) => aoArrastar(evento, true)}
        onDragOver={(evento) => aoArrastar(evento, true)}
        onDragLeave={(evento) => aoArrastar(evento, false)}
        onDrop={aoSoltar}
        className={cx(
          'flex min-h-55 flex-col items-center justify-center gap-2 rounded-lg border-2 px-6 py-8 text-center transition-colors',
          arquivo ? 'border-solid border-primary bg-selected' : 'border-dashed',
          !arquivo && (arrastando ? 'border-primary bg-selected' : 'border-border-dashed bg-subtle'),
          erro && 'border-status-danger-fg',
        )}
      >
        {arquivo ? (
          <>
            <Icon name="doc" size={40} className="text-primary" />
            <p className="m-0 max-w-full truncate text-[17px] leading-tight font-semibold text-text">
              {arquivo.name}
            </p>
            <p className="m-0 font-mono text-sm text-text-secondary">{formatarTamanho(arquivo.size)}</p>
            <div className="mt-2 flex gap-2">
              <Button variant="secondary" size="S" onClick={abrirSeletor}>
                Trocar arquivo
              </Button>
              <Button variant="secondary" size="S" onClick={remover}>
                Remover
              </Button>
            </div>
          </>
        ) : (
          <>
            <Icon name="upload" size={40} className="text-primary" />
            <p className="m-0 text-[17px] leading-tight font-semibold text-text">
              Arraste o documento para cá
            </p>
            <p className="m-0 text-sm text-text-secondary">
              ou{' '}
              <button
                type="button"
                onClick={abrirSeletor}
                className="cursor-pointer font-semibold text-link underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
              >
                selecione um arquivo
              </button>
            </p>
            <p className="m-0 text-caption text-text-placeholder">{NOTA}</p>
          </>
        )}
      </div>

      {erro && (
        <p role="alert" className="m-0 flex items-start gap-2 text-sm text-status-danger-fg">
          <Icon name="alert" size={18} className="mt-px shrink-0" />
          {erro}
        </p>
      )}
    </div>
  )
}
