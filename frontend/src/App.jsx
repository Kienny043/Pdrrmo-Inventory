import { PackageSearch } from 'lucide-react'

// R1 placeholder shell — proves the design tokens, fonts, Tailwind v4
// pipeline and lucide-react all resolve. The real layout, router, auth
// and pages arrive from R2 onward.
export default function App() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-pd-gray px-4">
      <div className="bg-white border border-pd-border rounded-2xl shadow-sm p-10 max-w-md text-center">
        <div className="w-12 h-12 rounded-full bg-pd-navy/10 text-pd-navy flex items-center justify-center mx-auto mb-4">
          <PackageSearch size={24} />
        </div>
        <h1
          className="text-xl font-bold text-pd-navy"
          style={{ fontFamily: "'Sora', sans-serif" }}
        >
          Inventory &amp; Training Matrix
        </h1>
        <p className="text-sm text-pd-text-secondary mt-2">
          React frontend scaffold (R1). Design tokens, fonts and the dev API
          proxy are wired up; pages land in R2 onward.
        </p>
        <div className="flex justify-center gap-2 mt-6">
          <span className="w-4 h-4 rounded-full bg-pd-navy" />
          <span className="w-4 h-4 rounded-full bg-pd-red" />
          <span className="w-4 h-4 rounded-full bg-pd-gold" />
          <span className="w-4 h-4 rounded-full bg-pd-green" />
        </div>
      </div>
    </div>
  )
}
