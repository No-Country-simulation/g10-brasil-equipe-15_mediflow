import logo from '../../assets/logo-mediflow.png'

/** Símbolo da logomarca + nome, sobre fundo escuro (sidebar e painel do login). */
export function MarcaMediFlow() {
  return (
    <div className="flex items-center gap-2.5">
      <img src={logo} alt="" width={43} height={32} className="h-8 w-auto" />
      <span className="text-xl font-semibold tracking-[-0.2px] text-sidebar-text-strong">MediFlow</span>
    </div>
  )
}
