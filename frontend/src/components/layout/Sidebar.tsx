import { Icon } from '../ui'
import { DemoNotice } from './DemoNotice'
import { NavItem } from './NavItem'
import { UserCard } from './UserCard'

/** Médica logada fictícia: a API ainda não tem autenticação. */
const USUARIO_MOCK = { nome: 'Dra. Renata Silveira', crm: 'CRM 145892 / SP' }

export function Sidebar() {
  return (
    <aside className="sticky top-0 flex h-screen w-58 shrink-0 flex-col gap-7 bg-sidebar px-4 py-6">
      <div className="flex w-full items-center gap-2.5 px-2">
        <Icon name="logo-marca" size={32} />
        <span className="text-xl font-semibold tracking-[-0.2px] text-sidebar-text-strong">MediFlow</span>
      </div>

      <nav aria-label="Principal" className="flex w-full flex-col gap-1">
        <NavItem to="/nova-triagem" label="Nova triagem" icon="plus" />
        <NavItem to="/triagens" label="Triagens e filas" icon="list" />
        <NavItem to="/meus-documentos" label="Meus documentos" icon="doc" />
      </nav>

      <div className="flex-1" />

      <UserCard {...USUARIO_MOCK} />
      <DemoNotice />
    </aside>
  )
}
