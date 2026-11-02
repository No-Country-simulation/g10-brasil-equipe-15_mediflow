import { PageHeader } from '../components/layout'

type PlaceholderPageProps = {
  title: string
  subtitle?: string
}

/** Tela ainda não implementada (depende de endpoints/fases futuras). */
export function PlaceholderPage({ title, subtitle }: PlaceholderPageProps) {
  return (
    <>
      <PageHeader title={title} subtitle={subtitle} />
      <div className="rounded-lg border border-border bg-surface p-7 text-text-secondary">
        Esta tela ainda não foi implementada.
      </div>
    </>
  )
}
