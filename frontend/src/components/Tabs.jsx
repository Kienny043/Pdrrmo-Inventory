// §2 "Tabs" — underline style, for in-page section switching (Archived
// page). `tabs` is an array of { key, label } or plain strings.
export default function Tabs({ tabs, active, onChange, className = '' }) {
  return (
    <div className={`bg-white border-b border-pd-border px-8 flex gap-6 ${className}`}>
      {tabs.map((t) => {
        const key = t.key ?? t
        const label = t.label ?? t
        const on = key === active
        return (
          <button
            key={key}
            type="button"
            onClick={() => onChange(key)}
            className={`py-3 text-sm font-medium border-b-2 transition-colors ${
              on
                ? 'border-pd-red text-pd-red'
                : 'border-transparent text-pd-text-secondary hover:text-pd-text-primary'
            }`}
          >
            {label}
          </button>
        )
      })}
    </div>
  )
}
