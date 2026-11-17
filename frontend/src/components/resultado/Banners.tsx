import type { Banner } from '../../lib/resultadoTriagem'
import { cx } from '../../lib/cx'
import { Icon } from '../ui'

const ESTILO = {
  sucesso: {
    caixa: 'border border-status-success-border bg-status-success-bg text-status-success-strong',
    titulo: 'text-status-success-strong',
    nota: 'text-status-success-strong',
    icone: 'check',
  },
  urgente: {
    caixa: 'bg-status-danger-solid text-on-primary',
    titulo: 'text-on-primary',
    nota: 'text-status-danger-soft-text',
    icone: 'alert',
  },
  revisao: {
    caixa: 'border border-status-warning-border bg-status-warning-bg text-status-warning-banner',
    titulo: 'text-status-warning-title',
    nota: 'text-status-warning-banner',
    icone: 'alert',
  },
} as const

/** Banner do topo do Resultado: sucesso (03a), urgente (03b/03c) ou revisão humana (03c/03d). */
export function BannerResultado({ banner }: { banner: Banner }) {
  const estilo = ESTILO[banner.tipo]
  return (
    <div
      role={banner.tipo === 'urgente' ? 'alert' : 'status'}
      className={cx('flex items-start gap-4 rounded-lg px-5.5 py-5', estilo.caixa)}
    >
      <Icon name={estilo.icone} size={24} className="mt-px shrink-0" />
      <div className="flex min-w-0 flex-col gap-1.5">
        <p className={cx('m-0 text-lg leading-snug font-semibold', estilo.titulo)}>{banner.titulo}</p>
        {banner.tipo === 'revisao' ? (
          <ul className="m-0 flex list-none flex-col p-0 text-[15px] leading-normal">
            {banner.itens.map((item) => (
              <li key={item}>•&nbsp;&nbsp;{item}</li>
            ))}
          </ul>
        ) : (
          banner.corpo && <p className="m-0 text-[15px] leading-normal">{banner.corpo}</p>
        )}
        {'nota' in banner && banner.nota && (
          <p className={cx('m-0 text-caption', estilo.nota)}>{banner.nota}</p>
        )}
      </div>
    </div>
  )
}
