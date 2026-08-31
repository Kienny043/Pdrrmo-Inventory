// §2 "Form inputs / selects" — one recipe for text/number/date/select/
// textarea inside a modal. Required fields get a literal " *" on the label.
// `error` renders a per-field message under the control — kept from the
// current vanilla-JS frontend (design decision #5), not in the source app.

export const INPUT_CLASS =
  'w-full bg-white border border-pd-border rounded-lg px-3 py-2 text-sm'

export function Field({ label, required = false, error, children, className = '' }) {
  return (
    <div className={className}>
      {label != null && (
        <label className="text-xs text-pd-text-secondary block mb-1">
          {label}
          {required ? ' *' : ''}
        </label>
      )}
      {children}
      {error && <p className="text-xs text-pd-red mt-1">{error}</p>}
    </div>
  )
}

// Search / filter inputs OUTSIDE modals — rounder variant (§2).
export function SearchInput({ className = '', ...props }) {
  return (
    <input
      type="text"
      className={`bg-white border border-pd-border text-sm text-pd-text-primary rounded-xl px-4 py-2 w-56 outline-none focus:border-pd-navy/40 ${className}`}
      {...props}
    />
  )
}
