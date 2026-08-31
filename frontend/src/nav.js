import {
  Grid3x3,
  Package,
  Users,
  ArrowLeftRight,
  ClipboardList,
  GraduationCap,
  Archive,
  Tags,
} from 'lucide-react'

// Order + role gating match the Django template nav (core/base.html)
// exactly: ADMIN sees all 8, STAFF sees only Equipment / Requests / Trainings.
export const NAV_ITEMS = [
  { label: 'Personnel', path: '/personnel', icon: Grid3x3, adminOnly: true },
  { label: 'Equipment', path: '/equipment', icon: Package },
  { label: 'Staff', path: '/staff', icon: Users, adminOnly: true },
  { label: 'Stock', path: '/movements', icon: ArrowLeftRight, adminOnly: true },
  { label: 'Requests', path: '/requests', icon: ClipboardList },
  { label: 'Trainings', path: '/trainings', icon: GraduationCap },
  { label: 'Archived', path: '/archived', icon: Archive, adminOnly: true },
  { label: 'Categories', path: '/categories', icon: Tags, adminOnly: true },
]

export const navItemsFor = (user) =>
  NAV_ITEMS.filter((item) => !item.adminOnly || user?.is_admin)
