// Class strings verbatim from docs/design-system-export.md §2 "Buttons".
// primary = the one solid-fill button in the app (navy). secondary = outline,
// pairs with primary in modal footers. chip = filter/toggle button.
// There is deliberately NO red variant (see §5 — never a solid red button).

const VARIANTS = {
  primary:
    'bg-pd-navy hover:bg-pd-navy/90 text-white text-sm font-semibold px-5 py-2 rounded-xl transition-all disabled:opacity-50',
  secondary:
    'px-4 py-2 text-sm border border-pd-border rounded-lg disabled:opacity-50',
}

export default function Button({
  variant = 'primary',
  active = false,
  type = 'button',
  className = '',
  ...props
}) {
  if (variant === 'chip') {
    const chip = active
      ? 'px-3 py-1.5 rounded-lg text-xs font-semibold bg-pd-navy text-white transition-colors'
      : 'px-3 py-1.5 rounded-lg text-xs font-semibold bg-white border border-pd-border text-pd-text-secondary hover:bg-pd-gray transition-colors'
    return <button type={type} className={`${chip} ${className}`} {...props} />
  }
  const base = VARIANTS[variant] || VARIANTS.primary
  return <button type={type} className={`${base} ${className}`} {...props} />
}
