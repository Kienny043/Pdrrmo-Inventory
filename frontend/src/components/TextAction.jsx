// Small text-link row actions (§2 / §5). Destructive + state-changing
// actions are colored text, never solid buttons. `confirm` shows a
// window.confirm() before firing — use shouty copy for irreversible ones.

const TONES = {
  navy: 'text-xs text-pd-navy hover:text-pd-navy/80 font-medium disabled:opacity-50',
  red: 'text-xs text-red-600 hover:text-red-800 font-medium disabled:opacity-50',
  green: 'text-xs text-green-600 hover:text-green-800 font-medium disabled:opacity-50',
  muted: 'text-xs text-pd-text-secondary hover:text-pd-navy font-medium disabled:opacity-50',
}

export default function TextAction({
  tone = 'navy',
  confirm,
  onClick,
  className = '',
  ...props
}) {
  const handle = (e) => {
    if (confirm && !window.confirm(confirm)) return
    onClick?.(e)
  }
  return (
    <button
      type="button"
      className={`${TONES[tone] || TONES.navy} ${className}`}
      onClick={handle}
      {...props}
    />
  )
}
