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
    // Abaixo de 1024px (fora do Figma, que é só desktop) a sidebar vira um bloco no topo da página.
    <aside className="flex w-full shrink-0 flex-col gap-4 bg-sidebar px-4 py-4 lg:sticky lg:top-0 lg:h-screen lg:w-58 lg:gap-7 lg:py-6">
      <div className="flex w-full items-center gap-2.5 px-2">
        <Icon name="logo-marca" size={32} />
        <span className="text-xl font-semibold tracking-[-0.2px] text-sidebar-text-strong">MediFlow</span>
      </div>

      <nav aria-label="Principal" className="flex w-full flex-wrap gap-1 lg:flex-col lg:flex-nowrap">
        <NavItem to="/nova-triagem" label="Nova triagem" icon="plus" />
        <NavItem to="/triagens" label="Triagens e filas" icon="list" />
        <NavItem to="/meus-documentos" label="Meus documentos" icon="doc" />
      </nav>

      <div className="hidden flex-1 lg:block" />

      <div className="grid gap-3 sm:grid-cols-2 lg:flex lg:flex-col lg:gap-7">
        <UserCard
          nome={nome}
          crm={crm}
          onSair={() => {
            sair()
            navigate('/login', { replace: true })
          }}
        />
        <DemoNotice />
      </div>
    </aside>
  )
}
