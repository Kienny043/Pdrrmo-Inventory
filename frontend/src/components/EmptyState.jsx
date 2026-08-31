// §5 "Empty states" — centered, muted, generous padding, no icon.
// Copy should be a short specific sentence: "No {things}." / "No {things} yet."
export default function EmptyState({ children }) {
  return <p className="text-center text-pd-text-secondary py-24">{children}</p>
}
