// §5 "Loading states". Spinner = the bare red ring. LoadingSection = the
// full-section "Loading..." block for page/table loads. FullScreenSpinner
// = the auth-check spinner (larger, centered, no text).

export function Spinner({ className = 'w-5 h-5' }) {
  return (
    <div
      className={`${className} border-2 border-pd-red border-t-transparent rounded-full animate-spin`}
    />
  )
}

export function LoadingSection({ label = 'Loading...' }) {
  return (
    <div className="flex justify-center py-24 text-pd-text-secondary">
      <Spinner className="w-5 h-5 mr-3" />
      {label}
    </div>
  )
}

export function FullScreenSpinner() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-pd-gray">
      <Spinner className="w-8 h-8" />
    </div>
  )
}
