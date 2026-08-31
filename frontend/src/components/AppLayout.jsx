// §3 "Shell structure" — Variant A: one shell renders the sidebar once and
// an <Outlet/> for the routed page.
import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'

export default function AppLayout() {
  return (
    <div
      className="flex min-h-screen bg-pd-gray text-pd-text-primary"
      style={{ fontFamily: "'DM Sans', sans-serif" }}
    >
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <Outlet />
      </div>
    </div>
  )
}
