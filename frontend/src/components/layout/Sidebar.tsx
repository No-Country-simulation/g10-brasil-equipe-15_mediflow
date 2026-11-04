import { useNavigate } from 'react-router'
import { useSessao } from '../../hooks/useSessao'
import { CRM_LOGADO_TEXTO, MEDICO_LOGADO } from '../../lib/medicoLogado'
import { Icon } from '../ui'
import { DemoNotice } from './DemoNotice'
import { NavItem } from './NavItem'
import { UserCard } from './UserCard'


export function Sidebar() {
  const { sessao, sair } = useSessao()
  const navigate = useNavigate()
  // Login de demonstração (Fase 5): o médico vem da sessão; o mock é só o valor de segurança.
  const nome = sessao?.medico.nome ?? MEDICO_LOGADO.nome
  const crm = sessao ? `CRM ${sessao.medico.crm.numero} / ${sessao.medico.crm.uf}` : CRM_LOGADO_TEXTO

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

      <UserCard
        nome={nome}
        crm={crm}
        onSair={() => {
          sair()
          navigate('/login', { replace: true })
        }}
      />
      <DemoNotice />
    </aside>
  )
}
