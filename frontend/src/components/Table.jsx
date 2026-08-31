// §2 "Tables" — one recipe everywhere. Table renders the card wrapper +
// horizontal-scroll container + <table>. Compose <THead>/<Th> and
// <tbody> with <Tr>/<Td> inside.

export function Table({ className = '', children }) {
  return (
    <div
      className={`bg-white border border-pd-border rounded-2xl overflow-hidden shadow-sm ${className}`}
    >
      <div className="overflow-x-auto">
        <table className="w-full text-sm">{children}</table>
      </div>
    </div>
  )
}

export function THead({ children }) {
  return (
    <thead>
      <tr className="border-b border-pd-border">{children}</tr>
    </thead>
  )
}

export function Th({ className = '', children, ...props }) {
  return (
    <th
      className={`text-left text-[11px] font-semibold text-pd-text-secondary uppercase tracking-wider px-4 py-3 ${className}`}
      {...props}
    >
      {children}
    </th>
  )
}

// `tint` adds a permanent semantic row background (e.g. "bg-pd-red/5" for
// low stock) on top of the hover state.
export function Tr({ tint = '', className = '', children, ...props }) {
  return (
    <tr
      className={`border-b border-pd-border hover:bg-pd-gray transition-colors ${tint} ${className}`}
      {...props}
    >
      {children}
    </tr>
  )
}

const TD_VARIANT = {
  strong: 'font-medium',
  muted: 'text-pd-text-secondary',
  plain: '',
}

export function Td({ variant = 'strong', className = '', children, ...props }) {
  return (
    <td className={`px-4 py-3 ${TD_VARIANT[variant] ?? ''} ${className}`} {...props}>
      {children}
    </td>
  )
}
