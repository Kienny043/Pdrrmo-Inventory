// §3 "Sidebar structure" — fixed navy sidebar, brand block, role-filtered
// nav list, user-initial avatar + sign-out footer. Active-nav treatment is
// the Admin/Inventory tinted-pill-with-border variant.
//
// Note: PDRRMO_v3's sidebar has an <img src="/logo.png"> in the brand
// block; this repo has no logo asset (design export §4), so the brand is
// a text wordmark for now.
import { NavLink, useNavigate } from 'react-router-dom'
import { LogOut } from 'lucide-react'
import { useAuth } from '../lib/auth'
import { navItemsFor } from '../nav'

function initials(name = '') {
  const parts = name.trim().split(/[\s._-]+/).filter(Boolean)
  if (parts.length === 0) return '?'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[1][0]).toUpperCase()
}

function NavItem({ to, icon: Icon, label }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-medium transition-colors ${
          isActive
            ? 'bg-pd-red/10 text-pd-red border border-pd-red/20'
            : 'text-pd-gray hover:text-white hover:bg-white/10'
        }`
      }
    >
      <Icon size={20} strokeWidth={2} />
      {label}
    </NavLink>
  )
}

export default function Sidebar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const items = navItemsFor(user)

  const signOut = () => {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <aside className="w-56 bg-pd-navy border-r border-pd-border flex flex-col flex-shrink-0 h-screen sticky top-0">
      <div className="flex items-center gap-2 px-5 py-6 border-b border-pd-border">
        <div className="h-8 w-8 rounded-lg bg-white/10 flex items-center justify-center text-white text-xs font-bold">
          PD
        </div>
        <div>
          <div
            className="text-xs font-bold text-white tracking-wide"
            style={{ fontFamily: "'Sora', sans-serif" }}
          >
            PDRRMO
          </div>
          <div className="text-[10px] text-pd-gray">Inventory &amp; Training</div>
        </div>
      </div>

      <nav className="flex-1 px-3 py-4 flex flex-col gap-1 overflow-y-auto">
        {items.map((item) => (
          <NavItem key={item.path} to={item.path} icon={item.icon} label={item.label} />
        ))}
      </nav>

      <div className="border-t border-pd-border p-4">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-8 h-8 rounded-full bg-pd-gold/20 flex items-center justify-center flex-shrink-0 text-xs font-bold text-pd-gold">
            {initials(user?.username)}
          </div>
          <div className="min-w-0">
            <div className="text-xs font-semibold text-white truncate">
              {user?.username}
            </div>
            <div className="text-[10px] text-pd-gray truncate">
              {user?.is_admin ? 'Admin' : 'Staff'}
            </div>
          </div>
        </div>
        <button
          type="button"
          onClick={signOut}
          className="w-full flex items-center gap-2 text-xs text-pd-gray hover:text-pd-red hover:bg-pd-red/10 px-3 py-2 rounded-lg transition-colors"
        >
          <LogOut size={14} strokeWidth={2} />
          Sign out
        </button>
      </div>
    </aside>
  )
}
