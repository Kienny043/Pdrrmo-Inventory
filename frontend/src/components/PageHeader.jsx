// §3 "Page-container conventions" — the sticky white header (Sora title
// + muted subtitle + right-aligned actions) and the scrollable body.

export default function PageHeader({ title, subtitle, actions }) {
  return (
    <header className="bg-white border-b border-pd-border px-8 py-4 flex items-center justify-between gap-4 sticky top-0 z-20">
      <div>
        <h1
          className="text-lg font-bold text-pd-text-primary"
          style={{ fontFamily: "'Sora', sans-serif" }}
        >
          {title}
        </h1>
        {subtitle != null && subtitle !== '' && (
          <p className="text-xs text-pd-text-secondary mt-0.5">{subtitle}</p>
        )}
      </div>
      {actions && <div className="flex items-center gap-3">{actions}</div>}
    </header>
  )
}

export function PageBody({ className = '', children }) {
  return (
    <main className={`flex-1 px-8 py-6 overflow-y-auto ${className}`}>{children}</main>
  )
}
