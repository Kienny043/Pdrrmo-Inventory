// Client-side CSV export. `columns` is [{ label, key }] or
// [{ label, get: row => value }]. Triggers a browser download.
function esc(v) {
  v = v == null ? '' : String(v)
  return /[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v
}

export function downloadCsv(filename, rows, columns) {
  const head = columns.map((c) => esc(c.label)).join(',')
  const body = rows
    .map((r) => columns.map((c) => esc(c.get ? c.get(r) : r[c.key])).join(','))
    .join('\n')
  const blob = new Blob([`${head}\n${body}`], { type: 'text/csv;charset=utf-8' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  document.body.appendChild(a)
  a.click()
  setTimeout(() => {
    URL.revokeObjectURL(a.href)
    a.remove()
  }, 0)
}
