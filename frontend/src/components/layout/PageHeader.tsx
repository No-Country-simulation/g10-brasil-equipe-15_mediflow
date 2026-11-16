type PageHeaderProps = {
  title: string
  subtitle?: string
}

export function PageHeader({ title, subtitle }: PageHeaderProps) {
  return (
    <header className="flex flex-col gap-1.5">
      <h1 className="text-heading font-semibold text-text">{title}</h1>
      {subtitle && <p className="m-0 max-w-170 text-body text-text-secondary">{subtitle}</p>}
    </header>
  )
}
