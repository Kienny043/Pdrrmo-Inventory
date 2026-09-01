import { useEffect, useState } from 'react'
import { apiGet } from '../lib/api'
import { Table, THead, Th, Tr, Td } from './Table'
import Button from './Button'
import Badge from './Badge'
import Modal from './Modal'
import ErrorBanner from './ErrorBanner'
import { LoadingSection } from './Spinner'
import EmptyState from './EmptyState'

// Holder-history for an InventoryItem. Works for active and archived items
// alike (the endpoint reads the unfiltered queryset). Shared by the
// Equipment dashboard and the Archived page's Items tab.
export default function ItemHistoryModal({ item, open, onClose }) {
  const [logs, setLogs] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open || !item) return
    setLogs(null)
    setError('')
    apiGet(`/api/items/${item.id}/holder-history/`).then(setLogs).catch((e) => setError(e.message))
  }, [open, item])

  return (
    <Modal open={open} onClose={onClose} title={item ? `Holder history — ${item.name}` : ''} size="xl">
      {error && <ErrorBanner>{error}</ErrorBanner>}
      {!logs ? (
        <LoadingSection />
      ) : logs.length === 0 ? (
        <EmptyState>No holder history.</EmptyState>
      ) : (
        <Table>
          <THead>
            <Th>When</Th>
            <Th>Action</Th>
            <Th>Staff</Th>
            <Th>By</Th>
            <Th>Note</Th>
          </THead>
          <tbody>
            {logs.map((h) => (
              <Tr key={h.id}>
                <Td variant="muted">{String(h.timestamp).slice(0, 10)}</Td>
                <Td variant="plain">
                  <Badge value={h.action} />
                </Td>
                <Td>{h.staff_name || '—'}</Td>
                <Td variant="muted">{h.performed_by || '—'}</Td>
                <Td variant="muted">{h.note || '—'}</Td>
              </Tr>
            ))}
          </tbody>
        </Table>
      )}
      <div className="flex justify-end mt-4">
        <Button variant="secondary" onClick={onClose}>
          Close
        </Button>
      </div>
    </Modal>
  )
}
