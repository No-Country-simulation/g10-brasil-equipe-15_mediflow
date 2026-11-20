import { useId } from 'react'

type TextoClinicoInputProps = {
  value: string
  onChange: (valor: string) => void
}

function rotuloContador(total: number): string {
  return `${total.toLocaleString('pt-BR')} ${total === 1 ? 'caractere' : 'caracteres'}`
}

export function TextoClinicoInput({ value, onChange }: TextoClinicoInputProps) {
  const id = useId()

  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={id} className="text-sm leading-none font-semibold text-text">
        Conteúdo do documento
      </label>
      <textarea
        id={id}
        value={value}
        onChange={(evento) => onChange(evento.target.value)}
        placeholder="Cole aqui o texto do documento clínico."
        aria-describedby={`${id}-contador`}
        spellCheck={false}
        className="h-58 w-full resize-y rounded-md border border-border-input bg-surface p-3.5 text-[15px] leading-normal text-text placeholder:text-text-placeholder focus-visible:border-primary focus-visible:outline-2 focus-visible:-outline-offset-1 focus-visible:outline-primary"
      />
      <p id={`${id}-contador`} className="m-0 text-caption text-text-placeholder">
        {rotuloContador(value.length)}
      </p>
    </div>
  )
}
