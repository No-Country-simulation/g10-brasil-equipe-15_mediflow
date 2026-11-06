import { Outlet } from 'react-router'
import { Sidebar } from './Sidebar'

export function AppLayout() {
  return (
    <div className="flex min-h-screen bg-app">
      <Sidebar />
      <main className="flex min-w-0 flex-1 flex-col gap-7 px-12 pt-10 pb-14">
        <Outlet />
      </main>
    </div>
  )
}
