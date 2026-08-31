// §5 "Error / alert banners" — soft red tint, never solid. Used for
// login failures and post-submit business errors. Renders nothing when
// there's no message.
import { AlertCircle } from 'lucide-react'

export default function ErrorBanner({ children }) {
  if (!children) return null
  return (
    <div className="flex items-start gap-3 bg-pd-red/10 border border-pd-red/20 rounded-xl px-4 py-3">
      <AlertCircle className="w-4 h-4 text-pd-red mt-0.5 flex-shrink-0" />
      <p className="text-sm text-pd-red">{children}</p>
    </div>
  )
}
