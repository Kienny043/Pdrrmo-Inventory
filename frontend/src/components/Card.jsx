// §2 "Content card" — wraps a form section or any boxed content.
// (The table recipe has its own wrapper in Table.jsx.)
export default function Card({ className = '', children, ...props }) {
  return (
    <div
      className={`bg-white border border-pd-border rounded-2xl shadow-sm ${className}`}
      {...props}
    >
      {children}
    </div>
  )
}
