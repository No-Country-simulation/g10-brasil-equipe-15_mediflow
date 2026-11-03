import { Link } from 'react-router'

/** Painel azul do Figma: avisa que a triagem continua no servidor se a pessoa sair da tela. */
export function AvisoSaidaDaTela() {
  return (
    <aside className="flex flex-col gap-2 rounded-lg border border-border-info bg-selected p-5">
      <h2 className="m-0 text-[15px] leading-tight font-semibold text-text">Pode sair desta tela</h2>
      <p className="m-0 text-sm leading-normal text-info-panel-text">
        A triagem continua no servidor. O resultado fica disponível pelo ID em{' '}
        <Link to="/triagens" className="text-link hover:underline">
          Triagens e filas
        </Link>
        .
      </p>
    </aside>
  )
}
