import { Outlet } from 'react-router'
import { Sidebar } from './Sidebar'

export function AppLayout() {
  return (
    <div className="flex min-h-screen flex-col bg-app lg:flex-row">
      <Sidebar />
      <main className="flex min-w-0 flex-1 flex-col gap-7 px-4 pt-6 pb-10 sm:px-8 lg:px-12 lg:pt-10 lg:pb-14">
        <Outlet />
      </main>
    </div>
  )
}
