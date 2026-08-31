// §2 "Badges / status pills" — shape is fixed; color pair swapped per
// status value. Map lifted from the design export's badge table, extended
// for this project's own enums (training schedule/registration status).
// Convention: green = good, blue = neutral, yellow = caution, red = final.

const STATUS_CLASS = {
  // inventory item condition
  NEW: 'bg-green-100 text-green-700',
  GOOD: 'bg-blue-100 text-blue-700',
  FAIR: 'bg-yellow-100 text-yellow-700',
  NEEDS_REPAIR: 'bg-red-100 text-red-700',
  DAMAGED: 'bg-red-100 text-red-700',
  // staff status
  PERMANENT: 'bg-pd-green/10 text-pd-green',
  CASUAL: 'bg-pd-gold/10 text-pd-gold',
  INTERN: 'bg-blue-100 text-blue-700',
  INACTIVE: 'bg-red-100 text-red-700',
  // inventory request status
  PENDING: 'bg-yellow-100 text-yellow-700',
  APPROVED: 'bg-green-100 text-green-700',
  REJECTED: 'bg-red-100 text-red-700',
  // personnel org affiliation
  EMPLOYEE: 'bg-blue-100 text-blue-700',
  VOLUNTEER: 'bg-green-100 text-green-700',
  // training schedule status
  UPCOMING: 'bg-blue-100 text-blue-700',
  ONGOING: 'bg-yellow-100 text-yellow-700',
  COMPLETED: 'bg-green-100 text-green-700',
  CANCELLED: 'bg-red-100 text-red-700',
  // training registration status
  REGISTERED: 'bg-green-100 text-green-700',
  // item holder log action
  ASSIGNED: 'bg-green-100 text-green-700',
  REMOVED: 'bg-red-100 text-red-700',
}

const FALLBACK = 'bg-pd-gray text-pd-text-secondary'

export default function Badge({ value, label, className = '' }) {
  const cls = STATUS_CLASS[value] || FALLBACK
  return (
    <span
      className={`text-xs font-semibold px-2 py-0.5 rounded-full ${cls} ${className}`}
    >
      {label ?? value}
    </span>
  )
}
