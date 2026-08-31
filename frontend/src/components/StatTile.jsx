// §2 "Stat tile" — dashboard summary number. The number's color carries
// meaning; label is uppercase + letter-spaced under it.
const NUM_COLOR = {
  navy: 'text-pd-navy',
  red: 'text-pd-red',
  gold: 'text-pd-gold',
  blue: 'text-blue-600',
}

export default function StatTile({ value, label, color = 'navy' }) {
  return (
    <div className="bg-white border border-pd-border rounded-2xl p-5 shadow-sm">
      <div
        className={`text-2xl font-bold ${NUM_COLOR[color] || NUM_COLOR.navy}`}
        style={{ fontFamily: "'Sora', sans-serif" }}
      >
        {value}
      </div>
      <div className="text-xs text-pd-text-secondary uppercase tracking-wider mt-1">
        {label}
      </div>
    </div>
  )
}
