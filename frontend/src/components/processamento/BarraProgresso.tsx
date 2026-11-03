type BarraProgressoProps = {
  /** 0 a 100 */
  porcentagem: number
  rotulo: string
}

export function BarraProgresso({ porcentagem, rotulo }: BarraProgressoProps) {
  const valor = Math.min(100, Math.max(0, Math.round(porcentagem)))

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-baseline justify-between gap-4 text-caption text-text-secondary">
        <span>{rotulo}</span>
        <span>{valor}%</span>
      </div>
      <div
        role="progressbar"
        aria-label="Progresso da triagem"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={valor}
        className="h-2 overflow-hidden rounded-full bg-progress-track"
      >
        <div
          className="h-full rounded-full bg-primary transition-[width] duration-500 motion-reduce:transition-none"
          style={{ width: `${valor}%` }}
        />
      </div>
    </div>
  )
}
