import { useEffect, useRef, useState } from 'react'
import { Button } from '../ui'

/** Painel "Ver JSON da resposta": a resposta da API como veio, formatada. */
export function PainelJson({ id, dados }: { id: string; dados: unknown }) {
  const texto = JSON.stringify(dados, null, 2)
  const [copiado, setCopiado] = useState<'ocioso' | 'ok' | 'falhou'>('ocioso')
  const temporizador = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  useEffect(() => () => clearTimeout(temporizador.current), [])

  async function copiar() {
    try {
      await navigator.clipboard.writeText(texto)
      setCopiado('ok')
    } catch {
      setCopiado('falhou')
    }
    clearTimeout(temporizador.current)
    temporizador.current = setTimeout(() => setCopiado('ocioso'), 2000)
  }

  return (
    <section id={id} aria-label="JSON da resposta" className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-5.5">
      <div className="flex items-center justify-between gap-3">
        <h2 className="m-0 text-base font-semibold text-text">JSON da resposta</h2>
        <Button variant="secondary" size="S" onClick={copiar}>
          <span aria-live="polite">{copiado === 'ok' ? 'JSON copiado' : copiado === 'falhou' ? 'Não foi possível copiar' : 'Copiar JSON'}</span>
        </Button>
      </div>
      <pre className="m-0 max-h-120 overflow-auto rounded-md bg-subtle p-4 font-mono text-xs leading-normal text-text-body">
        {texto}
      </pre>
    </section>
  )
}
