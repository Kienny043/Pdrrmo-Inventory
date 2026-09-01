import { useEffect, useState } from 'react'
import { apiGet } from '../lib/api'
import { Table, THead, Th, Tr, Td } from './Table'
import Button from './Button'
import Badge from './Badge'
import Modal from './Modal'
import ErrorBanner from './ErrorBanner'
import { LoadingSection } from './Spinner'

const yn = (v) => (v ? '✓' : '—')

// Read-only attendance record for a training — registrations, the Personnel
// roster, and manual attendees. Reuses the three GET endpoints the Trainings
// page's RosterPanel calls; no editing here. Used by the Archived page so an
// archived training's history is inspectable without restoring it first.
export default function TrainingHistoryModal({ training, open, onClose }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open || !training) return
    setData(null)
    setError('')
    Promise.all([
      apiGet(`/api/trainings/${training.id}/registrations/`),
      apiGet(`/api/trainings/${training.id}/personnel-attendees/`),
      apiGet(`/api/trainings/${training.id}/manual-attendees/`),
    ])
      .then(([regs, roster, manual]) => setData({ regs, roster, manual }))
      .catch((e) => setError(e.message))
  }, [open, training])

  const Section = ({ title, note, children }) => (
    <div className="mb-5">
      <h3 className="text-sm font-bold mb-1" style={{ fontFamily: "'Sora', sans-serif" }}>
        {title}
      </h3>
      {note && <p className="text-xs text-pd-text-secondary mb-2">{note}</p>}
      {children}
    </div>
  )

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={training ? `Training history — ${training.title}` : ''}
      size="2xl"
    >
      {error && <ErrorBanner>{error}</ErrorBanner>}
      {!data ? (
        <LoadingSection />
      ) : (
        <>
          <Section title="Registrations">
            {data.regs.length === 0 ? (
              <p className="text-xs text-pd-text-secondary">No registrations.</p>
            ) : (
              <Table>
                <THead>
                  <Th>User</Th>
                  <Th>Status</Th>
                  <Th>Registered</Th>
                  <Th>Attended</Th>
                </THead>
                <tbody>
                  {data.regs.map((r) => (
                    <Tr key={r.id}>
                      <Td>{r.user}</Td>
                      <Td variant="plain"><Badge value={r.status} /></Td>
                      <Td variant="muted">{String(r.registered_at || '').slice(0, 10)}</Td>
                      <Td variant="muted">{yn(r.attended)}</Td>
                    </Tr>
                  ))}
                </tbody>
              </Table>
            )}
          </Section>

          <Section
            title="Personnel roster"
            note="Existing Personnel records added by an admin — attendance here fed the training matrix."
          >
            {data.roster.length === 0 ? (
              <p className="text-xs text-pd-text-secondary">No personnel on the roster.</p>
            ) : (
              <Table>
                <THead>
                  <Th>Name</Th>
                  <Th>Municipality</Th>
                  <Th>District</Th>
                  <Th>Attended</Th>
                </THead>
                <tbody>
                  {data.roster.map((pa) => (
                    <Tr key={pa.id}>
                      <Td>{pa.personnel_name}</Td>
                      <Td variant="muted">{pa.personnel_municipality}</Td>
                      <Td variant="muted">{pa.personnel_district || '—'}</Td>
                      <Td variant="muted">{yn(pa.attended)}</Td>
                    </Tr>
                  ))}
                </tbody>
              </Table>
            )}
          </Section>

          <Section
            title="Manual attendees"
            note="Free-typed walk-ins — did not feed the training matrix."
          >
            {data.manual.length === 0 ? (
              <p className="text-xs text-pd-text-secondary">No manual attendees.</p>
            ) : (
              <Table>
                <THead>
                  <Th>Name</Th>
                  <Th>Municipality</Th>
                  <Th>District</Th>
                  <Th>Affiliation</Th>
                  <Th>Attended</Th>
                </THead>
                <tbody>
                  {data.manual.map((a) => (
                    <Tr key={a.id}>
                      <Td>{a.name}</Td>
                      <Td variant="muted">{a.municipality}</Td>
                      <Td variant="muted">{a.district || '—'}</Td>
                      <Td variant="muted">{a.org_affiliation}</Td>
                      <Td variant="muted">{yn(a.attended)}</Td>
                    </Tr>
                  ))}
                </tbody>
              </Table>
            )}
          </Section>
        </>
      )}
      <div className="flex justify-end mt-2">
        <Button variant="secondary" onClick={onClose}>
          Close
        </Button>
      </div>
    </Modal>
  )
}
