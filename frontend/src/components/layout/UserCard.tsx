import { iniciais } from '../../lib/medicoLogado'
import { Icon } from '../ui'

type UserCardProps = {
  nome: string
  crm: string
  onSair?: () => void
}


export function UserCard({ nome, crm, onSair }: UserCardProps) {
  return (
    <div className="flex w-full flex-col gap-3 rounded-sm border border-sidebar-border p-3">
      <div className="flex items-center gap-2.5">
        <div
          aria-hidden="true"
          className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary text-[13px] font-medium text-on-primary"
        >
          {iniciais(nome)}
        </div>
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className="text-sm leading-tight font-semibold text-sidebar-text-strong">{nome}</span>
          <span className="font-mono text-xs text-sidebar-text">{crm}</span>
        </div>
      </div>
      <div className="h-px w-full bg-sidebar-border" />
      <button
        type="button"
        onClick={onSair}
        className="flex w-full items-center gap-2 text-left text-caption font-medium text-sidebar-text hover:text-sidebar-text-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
      >
        <Icon name="logout" size={18} />
        Sair da conta
      </button>
    </div>
  )
}
