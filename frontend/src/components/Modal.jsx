// §2 "Modals" — overlay + centered white card. Conditional render, no
// animation, no × button (Cancel / backdrop click close it). `footer`
// slot is right-aligned with gap-3 per the doc's modal footer.

const SIZES = { md: 'max-w-md', xl: 'max-w-xl', '2xl': 'max-w-2xl' }

export default function Modal({
  open,
  onClose,
  title,
  size = 'md',
  children,
  footer,
  closeOnBackdrop = true,
}) {
  if (!open) return null
  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4"
      onClick={(e) => {
        if (closeOnBackdrop && e.target === e.currentTarget) onClose?.()
      }}
    >
      <div
        className={`bg-white border border-pd-border rounded-2xl w-full ${
          SIZES[size] || SIZES.md
        } p-6 shadow-lg max-h-[85vh] overflow-y-auto`}
      >
        {title && <h3 className="text-lg font-bold mb-4">{title}</h3>}
        {children}
        {footer && <div className="flex justify-end gap-3 mt-2">{footer}</div>}
      </div>
    </div>
  )
}
