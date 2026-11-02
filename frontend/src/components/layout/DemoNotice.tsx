export function DemoNotice() {
  return (
    <aside className="flex w-full flex-col gap-1 rounded-sm border border-sidebar-border p-3 text-caption">
      <strong className="font-medium text-sidebar-text-strong">Ambiente de demonstração</strong>
      <p className="m-0 text-sidebar-text">
        Somente dados fictícios. Destinos e alertas são simulados — nada é enviado a sistemas externos.
      </p>
    </aside>
  )
}
