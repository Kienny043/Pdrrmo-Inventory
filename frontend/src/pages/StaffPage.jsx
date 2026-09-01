import { useCallback, useEffect, useState } from 'react'
import { apiGet, apiPost, apiPatch, apiDelete } from '../lib/api'
import PageHeader, { PageBody } from '../components/PageHeader'
import { Table, THead, Th, Tr, Td } from '../components/Table'
import { Field, INPUT_CLASS } from '../components/Field'
import Button from '../components/Button'
import TextAction from '../components/TextAction'
import Badge from '../components/Badge'
import Modal from '../components/Modal'
import ErrorBanner from '../components/ErrorBanner'
import { LoadingSection } from '../components/Spinner'
import EmptyState from '../components/EmptyState'

const STATUSES = [
  ['PERMANENT', 'Permanent'],
  ['CASUAL', 'Casual'],
  ['INTERN', 'Intern'],
  ['INACTIVE', 'Inactive'],
]

function StaffForm({ staff, onSaved, onCancel }) {
  const editing = !!staff
  const [values, setValues] = useState(() => ({
    first_name: staff?.first_name ?? '',
    last_name: staff?.last_name ?? '',
    position: staff?.position ?? '',
    department: staff?.department ?? '',
    contact: staff?.contact ?? '',
    status: staff?.status ?? 'PERMANENT',
  }))
  const [file, setFile] = useState(null)
  const [removePhoto, setRemovePhoto] = useState(false)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const set = (k) => (e) => setValues((v) => ({ ...v, [k]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      const fd = new FormData()
      Object.entries(values).forEach(([k, v]) => fd.append(k, v))
      if (file) fd.append('photo', file)
      if (editing && removePhoto) fd.append('remove_photo', 'true')
      if (editing) await apiPatch(`/api/staff/${staff.id}/`, fd)
      else await apiPost('/api/staff/', fd)
      onSaved()
    } catch (err) {
      setError(err.message)
      setSubmitting(false)
    }
  }

  return (
    <form className="flex flex-col gap-4" onSubmit={submit}>
      {error && <ErrorBanner>{error}</ErrorBanner>}
      <div className="grid grid-cols-2 gap-4">
        <Field label="First name" required>
          <input className={INPUT_CLASS} value={values.first_name} onChange={set('first_name')} required />
        </Field>
        <Field label="Last name" required>
          <input className={INPUT_CLASS} value={values.last_name} onChange={set('last_name')} required />
        </Field>
      </div>
      <Field label="Position">
        <input className={INPUT_CLASS} value={values.position} onChange={set('position')} />
      </Field>
      <div className="grid grid-cols-2 gap-4">
        <Field label="Department">
          <input className={INPUT_CLASS} value={values.department} onChange={set('department')} />
        </Field>
        <Field label="Contact">
          <input className={INPUT_CLASS} value={values.contact} onChange={set('contact')} />
        </Field>
      </div>
      <Field label="Status">
        <select className={INPUT_CLASS} value={values.status} onChange={set('status')}>
          {STATUSES.map(([v, label]) => (
            <option key={v} value={v}>
              {label}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Photo">
        <input
          type="file"
          accept="image/*"
          className="text-sm"
          onChange={(e) => setFile(e.target.files[0] || null)}
        />
      </Field>

      {/* Rendered only when a photo actually exists — conditional render, so
          the node is ABSENT from the DOM otherwise (fixes UI-audit Finding 1,
          which was a [hidden]-attribute defeated by CSS specificity). */}
      {editing && staff.photo && (
        <label className="flex items-center gap-2 text-xs text-pd-text-secondary">
          <input
            type="checkbox"
            name="remove_photo"
            checked={removePhoto}
            onChange={(e) => setRemovePhoto(e.target.checked)}
          />
          Remove current photo
        </label>
      )}

      <div className="flex justify-end gap-3 mt-2">
        <Button variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={submitting}>
          {submitting ? 'Saving…' : 'Save'}
        </Button>
      </div>
    </form>
  )
}

export default function StaffPage() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState(null)

  const load = useCallback(async () => {
    try {
      setRows(await apiGet('/api/staff/'))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const openCreate = () => {
    setEditing(null)
    setModalOpen(true)
  }
  const openEdit = (s) => {
    setEditing(s)
    setModalOpen(true)
  }
  const onSaved = async () => {
    setModalOpen(false)
    await load()
  }

  const archive = async (s) => {
    setError('')
    try {
      await apiDelete(`/api/staff/${s.id}/`)
      setRows((rs) => rs.filter((r) => r.id !== s.id))
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <>
      <PageHeader
        title="Staff Management"
        subtitle={loading ? '' : `${rows.length} staff`}
        actions={<Button onClick={openCreate}>+ New Staff</Button>}
      />
      <PageBody>
        {error && (
          <div className="mb-4">
            <ErrorBanner>{error}</ErrorBanner>
          </div>
        )}

        {loading ? (
          <LoadingSection />
        ) : rows.length === 0 ? (
          <EmptyState>No staff yet.</EmptyState>
        ) : (
          <Table>
            <THead>
              <Th className="w-14" />
              <Th>Name</Th>
              <Th>Position</Th>
              <Th>Department</Th>
              <Th>Contact</Th>
              <Th>Status</Th>
              <Th className="w-32" />
            </THead>
            <tbody>
              {rows.map((s) => (
                <Tr key={s.id}>
                  <Td variant="plain">
                    {s.photo ? (
                      <img src={s.photo} alt="" className="h-9 w-9 rounded-md object-cover" />
                    ) : (
                      <span className="text-pd-text-secondary">—</span>
                    )}
                  </Td>
                  <Td>{s.full_name}</Td>
                  <Td variant="muted">{s.position || '—'}</Td>
                  <Td variant="muted">{s.department || '—'}</Td>
                  <Td variant="muted">{s.contact || '—'}</Td>
                  <Td variant="plain">
                    <Badge value={s.status} />
                  </Td>
                  <Td variant="plain">
                    <div className="flex gap-3">
                      <TextAction tone="muted" onClick={() => openEdit(s)}>
                        Edit
                      </TextAction>
                      <TextAction
                        tone="red"
                        confirm={`Archive ${s.full_name}? They move to the Archived page.`}
                        onClick={() => archive(s)}
                      >
                        Archive
                      </TextAction>
                    </div>
                  </Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        )}
      </PageBody>

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editing ? `Edit ${editing.full_name}` : 'New Staff'}
      >
        {modalOpen && (
          <StaffForm
            key={editing?.id ?? 'new'}
            staff={editing}
            onSaved={onSaved}
            onCancel={() => setModalOpen(false)}
          />
        )}
      </Modal>
    </>
  )
}
