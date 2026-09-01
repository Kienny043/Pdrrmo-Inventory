import { Fragment, useCallback, useEffect, useState } from 'react'
import { apiGet, apiPost, apiPatch, apiDelete } from '../lib/api'
import { useAuth } from '../lib/auth'
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
  ['UPCOMING', 'Upcoming'],
  ['ONGOING', 'Ongoing'],
  ['COMPLETED', 'Completed'],
  ['CANCELLED', 'Cancelled'],
]
const SCALAR_FIELDS = [
  'title', 'description', 'date_start', 'date_end', 'time_start', 'time_end',
  'venue', 'target_participants', 'max_slots', 'registration_deadline', 'status',
]
const todayISO = () => new Date().toISOString().slice(0, 10)

// The 5 client-side register blockers (server 409 detail is also surfaced).
function registerBlock(t) {
  if (t.is_archived) return 'training is archived'
  if (t.status !== 'UPCOMING' && t.status !== 'ONGOING')
    return `registration closed (${t.status.toLowerCase()})`
  if (t.registration_deadline && t.registration_deadline < todayISO())
    return 'registration deadline passed'
  if (t.max_slots != null && t.registration_count >= t.max_slots) return 'training is full'
  if (t.my_registration_status === 'REGISTERED') return 'you are already registered'
  return null
}

function fmtDates(t) {
  let d = t.date_start
  if (t.date_end && t.date_end !== t.date_start) d += ` – ${t.date_end}`
  if (t.time_start) d += ` ${t.time_start.slice(0, 5)}${t.time_end ? `–${t.time_end.slice(0, 5)}` : ''}`
  return d
}

// --------------------------------------------------------------------------
// create / edit modal
// --------------------------------------------------------------------------

function TrainingForm({ training, catalog, onSaved, onCancel }) {
  const editing = !!training
  const [v, setV] = useState(() => {
    const base = {}
    SCALAR_FIELDS.forEach((f) => {
      let val = training?.[f] ?? ''
      if ((f === 'time_start' || f === 'time_end') && val) val = String(val).slice(0, 5)
      base[f] = val == null ? '' : String(val)
    })
    if (!editing) base.status = 'UPCOMING'
    return base
  })
  const [matrixKey, setMatrixKey] = useState(training?.matrix_training_key || '')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const set = (f) => (e) => setV((s) => ({ ...s, [f]: e.target.value }))

  const managerial = catalog.filter((c) => c.group === 'MANAGERIAL')
  const skills = catalog.filter((c) => c.group === 'SKILLS')

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      const data = { matrix_training_key: matrixKey }
      SCALAR_FIELDS.forEach((f) => {
        const val = v[f]
        if (f === 'max_slots') data[f] = val === '' ? null : Number(val)
        else if (['date_end', 'registration_deadline', 'time_start', 'time_end'].includes(f) && val === '')
          data[f] = null
        else data[f] = val
      })
      if (editing) await apiPatch(`/api/trainings/${training.id}/`, data)
      else await apiPost('/api/trainings/', data)
      onSaved()
    } catch (err) {
      setError(err.message)
      setSubmitting(false)
    }
  }

  return (
    <form className="flex flex-col gap-4" onSubmit={submit}>
      {error && <ErrorBanner>{error}</ErrorBanner>}
      <Field label="Title" required>
        <input className={INPUT_CLASS} value={v.title} onChange={set('title')} required />
      </Field>
      <Field label="Description">
        <textarea className={INPUT_CLASS} rows={2} value={v.description} onChange={set('description')} />
      </Field>
      <div className="grid grid-cols-2 gap-4">
        <Field label="Start date" required>
          <input type="date" className={INPUT_CLASS} value={v.date_start} onChange={set('date_start')} required />
        </Field>
        <Field label="End date">
          <input type="date" className={INPUT_CLASS} value={v.date_end} onChange={set('date_end')} />
        </Field>
        <Field label="Start time">
          <input type="time" className={INPUT_CLASS} value={v.time_start} onChange={set('time_start')} />
        </Field>
        <Field label="End time">
          <input type="time" className={INPUT_CLASS} value={v.time_end} onChange={set('time_end')} />
        </Field>
      </div>
      <Field label="Venue">
        <input className={INPUT_CLASS} value={v.venue} onChange={set('venue')} />
      </Field>
      <Field label="Target participants">
        <input className={INPUT_CLASS} value={v.target_participants} onChange={set('target_participants')} />
      </Field>
      <div className="grid grid-cols-2 gap-4">
        <Field label="Max slots">
          <input type="number" min="1" className={INPUT_CLASS} value={v.max_slots} onChange={set('max_slots')} />
        </Field>
        <Field label="Registration deadline">
          <input type="date" className={INPUT_CLASS} value={v.registration_deadline} onChange={set('registration_deadline')} />
        </Field>
      </div>
      <Field label="Status">
        <select className={INPUT_CLASS} value={v.status} onChange={set('status')}>
          {STATUSES.map(([val, label]) => (
            <option key={val} value={val}>{label}</option>
          ))}
        </select>
      </Field>
      <Field label="Matrix training key">
        <select className={INPUT_CLASS} value={matrixKey} onChange={(e) => setMatrixKey(e.target.value)}>
          <option value="">— none (event only) —</option>
          <optgroup label="MANAGERIAL">
            {managerial.map((c) => (
              <option key={c.key} value={c.key}>{c.label}</option>
            ))}
          </optgroup>
          <optgroup label="SKILLS">
            {skills.map((c) => (
              <option key={c.key} value={c.key}>{c.label}</option>
            ))}
          </optgroup>
        </select>
      </Field>
      <div className="flex justify-end gap-3 mt-2">
        <Button variant="secondary" onClick={onCancel}>Cancel</Button>
        <Button type="submit" disabled={submitting}>{submitting ? 'Saving…' : 'Save'}</Button>
      </div>
    </form>
  )
}

// --------------------------------------------------------------------------
// expandable ADMIN panel: roster + manual attendees
// --------------------------------------------------------------------------

// Search-as-you-type picker over existing Personnel records (all districts).
function PersonnelPicker({ excludeIds, onPick }) {
  const [q, setQ] = useState('')
  const [results, setResults] = useState([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const term = q.trim()
    if (!term) {
      setResults([])
      return
    }
    setLoading(true)
    const id = setTimeout(async () => {
      try {
        setResults(await apiGet(`/api/personnel/?search=${encodeURIComponent(term)}`))
      } catch {
        setResults([])
      } finally {
        setLoading(false)
      }
    }, 250)
    return () => clearTimeout(id)
  }, [q])

  const shown = results.filter((p) => !excludeIds.includes(p.id)).slice(0, 15)

  return (
    <div className="relative w-80">
      <input
        className={INPUT_CLASS}
        placeholder="Search personnel by name…"
        value={q}
        onChange={(e) => {
          setQ(e.target.value)
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
      />
      {open && q.trim() && (
        <div className="absolute z-20 mt-1 w-full bg-white border border-pd-border rounded-lg shadow-lg max-h-64 overflow-y-auto">
          {loading && <div className="px-3 py-2 text-xs text-pd-text-secondary">Searching…</div>}
          {!loading && shown.length === 0 && (
            <div className="px-3 py-2 text-xs text-pd-text-secondary">No matching personnel.</div>
          )}
          {shown.map((p) => (
            <button
              key={p.id}
              type="button"
              className="block w-full text-left px-3 py-2 text-sm hover:bg-pd-gray"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => {
                onPick(p)
                setQ('')
                setResults([])
                setOpen(false)
              }}
            >
              {p.name}
              <span className="text-pd-text-secondary">
                {' '}
                — {p.municipality} ({p.district})
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function RosterPanel({ training, municipalities }) {
  const [regs, setRegs] = useState(null)
  const [manual, setManual] = useState(null)
  const [roster, setRoster] = useState(null) // Personnel-roster attendees
  const [error, setError] = useState('')
  const [note, setNote] = useState({}) // registrations: { [user_id]: {text, tone} }
  const [rosterNote, setRosterNote] = useState({}) // roster: { [id]: {text, tone} }
  const [maForm, setMaForm] = useState({ name: '', designation: '', municipality: '', org_affiliation: 'EMPLOYEE' })

  const loadPanel = useCallback(async () => {
    try {
      const [r, m, pr] = await Promise.all([
        apiGet(`/api/trainings/${training.id}/registrations/`),
        apiGet(`/api/trainings/${training.id}/manual-attendees/`),
        apiGet(`/api/trainings/${training.id}/personnel-attendees/`),
      ])
      setRegs(r)
      setManual(m)
      setRoster(pr)
    } catch (e) {
      setError(e.message)
    }
  }, [training.id])

  useEffect(() => {
    loadPanel()
  }, [loadPanel])

  const toggleAttendance = async (reg, attended) => {
    setRegs((rs) => rs.map((x) => (x.id === reg.id ? { ...x, attended } : x))) // optimistic
    setNote((n) => ({ ...n, [reg.user_id]: { text: '…', tone: 'muted' } }))
    try {
      const resp = await apiPatch(`/api/trainings/${training.id}/attendance/${reg.user_id}/`, { attended })
      if (!attended) setNote((n) => ({ ...n, [reg.user_id]: { text: 'attendance cleared', tone: 'muted' } }))
      else if (resp.matrix_updated) setNote((n) => ({ ...n, [reg.user_id]: { text: '✓ matrix updated', tone: 'ok' } }))
      else setNote((n) => ({ ...n, [reg.user_id]: { text: `matrix not updated — ${resp.matrix_reason || 'no reason given'}`, tone: 'warn' } }))
    } catch (e) {
      setRegs((rs) => rs.map((x) => (x.id === reg.id ? { ...x, attended: !attended } : x))) // revert
      setNote((n) => ({ ...n, [reg.user_id]: { text: e.message, tone: 'warn' } }))
    }
  }

  const toggleManual = async (a, attended) => {
    setManual((ms) => ms.map((x) => (x.id === a.id ? { ...x, attended } : x))) // optimistic
    try {
      await apiPatch(`/api/trainings/${training.id}/manual-attendees/${a.id}/attendance/`, { attended })
    } catch (e) {
      setManual((ms) => ms.map((x) => (x.id === a.id ? { ...x, attended: !attended } : x))) // revert
      setError(e.message)
    }
  }

  const deleteManual = async (a) => {
    try {
      await apiDelete(`/api/trainings/${training.id}/manual-attendees/${a.id}/`)
      setManual((ms) => ms.filter((x) => x.id !== a.id))
    } catch (e) {
      setError(e.message)
    }
  }

  const addManual = async (e) => {
    e.preventDefault()
    setError('')
    try {
      await apiPost(`/api/trainings/${training.id}/manual-attendees/`, maForm)
      setMaForm({ name: '', designation: '', municipality: '', org_affiliation: 'EMPLOYEE' })
      await loadPanel()
    } catch (err) {
      setError(err.message)
    }
  }

  // --- Personnel-roster attendees ---
  const addRosterPersonnel = async (p) => {
    setError('')
    try {
      await apiPost(`/api/trainings/${training.id}/personnel-attendees/`, { personnel: p.id })
      await loadPanel()
    } catch (err) {
      setError(err.message) // e.g. "<name> is already on this training's roster."
    }
  }

  const toggleRoster = async (pa, attended) => {
    setRoster((rs) => rs.map((x) => (x.id === pa.id ? { ...x, attended } : x))) // optimistic
    setRosterNote((n) => ({ ...n, [pa.id]: { text: '…', tone: 'muted' } }))
    try {
      const resp = await apiPatch(
        `/api/trainings/${training.id}/personnel-attendees/${pa.id}/attendance/`,
        { attended }
      )
      if (!attended) setRosterNote((n) => ({ ...n, [pa.id]: { text: 'attendance cleared', tone: 'muted' } }))
      else if (resp.matrix_updated) setRosterNote((n) => ({ ...n, [pa.id]: { text: '✓ matrix updated', tone: 'ok' } }))
      else setRosterNote((n) => ({ ...n, [pa.id]: { text: `matrix not updated — ${resp.matrix_reason || 'no reason given'}`, tone: 'warn' } }))
    } catch (e) {
      setRoster((rs) => rs.map((x) => (x.id === pa.id ? { ...x, attended: !attended } : x))) // revert
      setRosterNote((n) => ({ ...n, [pa.id]: { text: e.message, tone: 'warn' } }))
    }
  }

  const deleteRoster = async (pa) => {
    try {
      await apiDelete(`/api/trainings/${training.id}/personnel-attendees/${pa.id}/`)
      setRoster((rs) => rs.filter((x) => x.id !== pa.id))
    } catch (e) {
      setError(e.message)
    }
  }

  const NOTE_CLASS = { ok: 'text-pd-green', warn: 'text-pd-red', muted: 'text-pd-text-secondary' }

  return (
    <div className="bg-pd-gray/60 px-4 py-4 flex flex-col gap-6">
      {error && <ErrorBanner>{error}</ErrorBanner>}

      <div>
        <h3 className="text-sm font-bold mb-2" style={{ fontFamily: "'Sora', sans-serif" }}>Registrations</h3>
        {!regs ? (
          <LoadingSection />
        ) : (
          <Table>
            <THead>
              <Th>User</Th>
              <Th>Status</Th>
              <Th>Registered</Th>
              <Th>Cancelled</Th>
              <Th>Attended</Th>
            </THead>
            <tbody>
              {regs.map((r) => (
                <Tr key={r.id}>
                  <Td>{r.user}</Td>
                  <Td variant="plain"><Badge value={r.status} /></Td>
                  <Td variant="muted">{String(r.registered_at || '').slice(0, 10)}</Td>
                  <Td variant="muted">{r.cancelled_at ? String(r.cancelled_at).slice(0, 10) : '—'}</Td>
                  <Td variant="plain">
                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={!!r.attended}
                        onChange={(e) => toggleAttendance(r, e.target.checked)}
                      />
                      {note[r.user_id] && (
                        <span className={`text-xs ${NOTE_CLASS[note[r.user_id].tone]}`}>
                          {note[r.user_id].text}
                        </span>
                      )}
                    </label>
                  </Td>
                </Tr>
              ))}
              {regs.length === 0 && (
                <tr>
                  <td colSpan={5}>
                    <p className="text-xs text-pd-text-secondary px-4 py-3">No registrations.</p>
                  </td>
                </tr>
              )}
            </tbody>
          </Table>
        )}
      </div>

      <div>
        <h3 className="text-sm font-bold mb-1" style={{ fontFamily: "'Sora', sans-serif" }}>Personnel roster</h3>
        <p className="text-xs text-pd-text-secondary mb-2">
          Existing Personnel records added by an admin. Attendance here <strong>does</strong> feed the
          training matrix (upserts their training-year cell), unlike manual attendees below.
        </p>
        {!roster ? (
          <LoadingSection />
        ) : (
          <Table>
            <THead>
              <Th>Name</Th>
              <Th>Municipality</Th>
              <Th>District</Th>
              <Th>Added by</Th>
              <Th>Attended</Th>
              <Th />
            </THead>
            <tbody>
              {roster.map((pa) => (
                <Tr key={pa.id}>
                  <Td>{pa.personnel_name}</Td>
                  <Td variant="muted">{pa.personnel_municipality}</Td>
                  <Td variant="muted">{pa.personnel_district || '—'}</Td>
                  <Td variant="muted">{pa.added_by || '—'}</Td>
                  <Td variant="plain">
                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={!!pa.attended}
                        onChange={(e) => toggleRoster(pa, e.target.checked)}
                      />
                      {rosterNote[pa.id] && (
                        <span className={`text-xs ${NOTE_CLASS[rosterNote[pa.id].tone]}`}>
                          {rosterNote[pa.id].text}
                        </span>
                      )}
                    </label>
                  </Td>
                  <Td variant="plain">
                    <TextAction
                      tone="red"
                      confirm={`Remove ${pa.personnel_name} from this training's roster?`}
                      onClick={() => deleteRoster(pa)}
                    >
                      Remove
                    </TextAction>
                  </Td>
                </Tr>
              ))}
              {roster.length === 0 && (
                <tr>
                  <td colSpan={6}>
                    <p className="text-xs text-pd-text-secondary px-4 py-3">No personnel on the roster.</p>
                  </td>
                </tr>
              )}
            </tbody>
          </Table>
        )}
        <div className="flex items-end gap-3 mt-3">
          <div>
            <label className="text-xs text-pd-text-secondary block mb-1">Add existing personnel</label>
            <PersonnelPicker
              excludeIds={(roster || []).map((pa) => pa.personnel)}
              onPick={addRosterPersonnel}
            />
          </div>
        </div>
      </div>

      <div>
        <h3 className="text-sm font-bold mb-1" style={{ fontFamily: "'Sora', sans-serif" }}>Manual attendees</h3>
        <p className="text-xs text-pd-text-secondary mb-2">
          Manual attendees do <strong>not</strong> feed the training matrix — their attendance is a plain record.
        </p>
        {!manual ? (
          <LoadingSection />
        ) : (
          <Table>
            <THead>
              <Th>Name</Th>
              <Th>Designation</Th>
              <Th>Municipality</Th>
              <Th>District</Th>
              <Th>Affiliation</Th>
              <Th>Attended</Th>
              <Th />
            </THead>
            <tbody>
              {manual.map((a) => (
                <Tr key={a.id}>
                  <Td>{a.name}</Td>
                  <Td variant="muted">{a.designation || '—'}</Td>
                  <Td variant="muted">{a.municipality}</Td>
                  <Td variant="muted">{a.district || '—'}</Td>
                  <Td variant="muted">{a.org_affiliation}</Td>
                  <Td variant="plain">
                    <input type="checkbox" checked={!!a.attended} onChange={(e) => toggleManual(a, e.target.checked)} />
                  </Td>
                  <Td variant="plain">
                    <TextAction tone="red" confirm={`Delete manual attendee “${a.name}”?`} onClick={() => deleteManual(a)}>
                      Delete
                    </TextAction>
                  </Td>
                </Tr>
              ))}
              {manual.length === 0 && (
                <tr><td colSpan={7}><p className="text-xs text-pd-text-secondary px-4 py-3">No manual attendees.</p></td></tr>
              )}
            </tbody>
          </Table>
        )}
        <form className="flex flex-wrap items-end gap-3 mt-3" onSubmit={addManual}>
          <Field label="Name" className="w-40">
            <input className={INPUT_CLASS} value={maForm.name} onChange={(e) => setMaForm({ ...maForm, name: e.target.value })} required />
          </Field>
          <Field label="Designation" className="w-40">
            <input className={INPUT_CLASS} value={maForm.designation} onChange={(e) => setMaForm({ ...maForm, designation: e.target.value })} />
          </Field>
          <Field label="Municipality" className="w-48">
            <select className={INPUT_CLASS} value={maForm.municipality} onChange={(e) => setMaForm({ ...maForm, municipality: e.target.value })} required>
              <option value="">— select —</option>
              {municipalities.map((m) => (
                <option key={m.name} value={m.name}>{m.name}</option>
              ))}
            </select>
          </Field>
          <Field label="Affiliation" className="w-36">
            <select className={INPUT_CLASS} value={maForm.org_affiliation} onChange={(e) => setMaForm({ ...maForm, org_affiliation: e.target.value })}>
              <option value="EMPLOYEE">Employee</option>
              <option value="VOLUNTEER">Volunteer</option>
            </select>
          </Field>
          <Button type="submit">Add attendee</Button>
        </form>
      </div>
    </div>
  )
}

// --------------------------------------------------------------------------
// page
// --------------------------------------------------------------------------

export default function TrainingsPage() {
  const { user } = useAuth()
  const isAdmin = !!user?.is_admin
  const canDelete = !!user?.can_permanently_delete

  const [trainings, setTrainings] = useState([])
  const [catalog, setCatalog] = useState([])
  const [municipalities, setMunicipalities] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [view, setView] = useState('active')
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [expandedId, setExpandedId] = useState(null)
  const [rowMsg, setRowMsg] = useState({}) // { [trainingId]: text } — register/cancel result
  const [rowBusy, setRowBusy] = useState({}) // { [trainingId]: bool } — register/cancel in flight

  const archived = view === 'archived'

  const load = useCallback(async () => {
    try {
      const [cat, muni, list] = await Promise.all([
        apiGet('/api/training-catalog/'),
        apiGet('/api/municipalities/'),
        apiGet(archived ? '/api/trainings/archived/' : '/api/trainings/'),
      ])
      setCatalog(cat)
      setMunicipalities(muni)
      setTrainings(list)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [archived])

  useEffect(() => {
    load()
  }, [load])

  const register = async (t) => {
    if (rowBusy[t.id]) return
    setRowMsg((m) => ({ ...m, [t.id]: '' }))
    setRowBusy((b) => ({ ...b, [t.id]: true }))
    try {
      await apiPost(`/api/trainings/${t.id}/register/`)
      await load()
    } catch (e) {
      setRowMsg((m) => ({ ...m, [t.id]: e.message }))
    } finally {
      setRowBusy((b) => ({ ...b, [t.id]: false }))
    }
  }
  const cancelReg = async (t) => {
    if (rowBusy[t.id]) return
    setRowMsg((m) => ({ ...m, [t.id]: '' }))
    setRowBusy((b) => ({ ...b, [t.id]: true }))
    try {
      await apiDelete(`/api/trainings/${t.id}/cancel-registration/`)
      await load()
    } catch (e) {
      setRowMsg((m) => ({ ...m, [t.id]: e.message }))
    } finally {
      setRowBusy((b) => ({ ...b, [t.id]: false }))
    }
  }
  const archive = async (t) => {
    try {
      await apiDelete(`/api/trainings/${t.id}/`)
      setExpandedId(null)
      await load()
    } catch (e) {
      setError(e.message)
    }
  }
  const restore = async (t) => {
    try {
      await apiPost(`/api/trainings/${t.id}/restore/`)
      await load()
    } catch (e) {
      setError(e.message)
    }
  }
  const permaDelete = async (t) => {
    try {
      await apiDelete(`/api/trainings/${t.id}/permanent-delete/`)
      await load()
    } catch (e) {
      setError(e.message)
    }
  }

  const COLS = 9

  return (
    <>
      <PageHeader
        title="Training Schedules"
        subtitle={loading ? '' : `${trainings.length} ${archived ? 'archived' : 'training'}${trainings.length === 1 ? '' : 's'}`}
        actions={
          isAdmin && (
            <>
              <select
                className={`${INPUT_CLASS} w-40`}
                value={view}
                onChange={(e) => {
                  setExpandedId(null)
                  setView(e.target.value)
                }}
              >
                <option value="active">Active</option>
                <option value="archived">Archived</option>
              </select>
              {!archived && (
                <Button
                  onClick={() => {
                    setEditing(null)
                    setModalOpen(true)
                  }}
                >
                  + New Training
                </Button>
              )}
            </>
          )
        }
      />
      <PageBody>
        {error && (
          <div className="mb-4">
            <ErrorBanner>{error}</ErrorBanner>
          </div>
        )}

        {loading ? (
          <LoadingSection />
        ) : trainings.length === 0 ? (
          <EmptyState>{archived ? 'No archived trainings.' : 'No trainings.'}</EmptyState>
        ) : (
          <Table>
            <THead>
              <Th>Title</Th>
              <Th>Dates</Th>
              <Th>Venue</Th>
              <Th>Status</Th>
              <Th>Matrix training</Th>
              <Th>Slots</Th>
              <Th>Deadline</Th>
              <Th>Regs</Th>
              <Th className="w-64" />
            </THead>
            <tbody>
              {trainings.map((t) => {
                const block = registerBlock(t)
                const registered = t.my_registration_status === 'REGISTERED'
                return (
                  <Fragment key={t.id}>
                    <Tr>
                      <Td>{t.title}</Td>
                      <Td variant="muted">{fmtDates(t)}</Td>
                      <Td variant="muted">{t.venue || '—'}</Td>
                      <Td variant="plain"><Badge value={t.status} /></Td>
                      <Td variant="muted">{t.matrix_training_label || '—'}</Td>
                      <Td variant="muted">{t.max_slots == null ? '—' : t.max_slots}</Td>
                      <Td variant="muted">{t.registration_deadline || '—'}</Td>
                      <Td>{t.registration_count}</Td>
                      <Td variant="plain">
                        <div className="flex flex-wrap items-center gap-3">
                          {registered ? (
                            <TextAction tone="red" disabled={!!rowBusy[t.id]} confirm={`Cancel your registration for “${t.title}”?`} onClick={() => cancelReg(t)}>
                              {rowBusy[t.id] ? 'Cancelling…' : 'Cancel registration'}
                            </TextAction>
                          ) : block ? (
                            <>
                              <span className="text-xs text-pd-text-secondary line-through opacity-60">Register</span>
                              <span className="text-xs text-pd-text-secondary">{block}</span>
                            </>
                          ) : (
                            <TextAction tone="navy" disabled={!!rowBusy[t.id]} onClick={() => register(t)}>
                              {rowBusy[t.id] ? 'Registering…' : 'Register'}
                            </TextAction>
                          )}
                          {t.my_registration_status && (
                            <span className="text-xs text-pd-text-secondary">you: {t.my_registration_status}</span>
                          )}

                          {isAdmin && !archived && (
                            <>
                              <TextAction tone="navy" onClick={() => setExpandedId(expandedId === t.id ? null : t.id)}>
                                {expandedId === t.id ? 'Hide' : 'Details'}
                              </TextAction>
                              <TextAction tone="muted" onClick={() => { setEditing(t); setModalOpen(true) }}>
                                Edit
                              </TextAction>
                              <TextAction tone="red" confirm={`Archive “${t.title}”?`} onClick={() => archive(t)}>
                                Archive
                              </TextAction>
                            </>
                          )}
                          {isAdmin && archived && (
                            <>
                              <TextAction tone="green" onClick={() => restore(t)}>Restore</TextAction>
                              {canDelete && (
                                <TextAction tone="red" confirm={`Permanently delete “${t.title}”? This cannot be undone. Its registrations, attendance, and roster will be permanently deleted too.`} onClick={() => permaDelete(t)}>
                                  Delete
                                </TextAction>
                              )}
                            </>
                          )}
                        </div>
                        {rowMsg[t.id] && <p className="text-xs text-pd-red mt-1">{rowMsg[t.id]}</p>}
                      </Td>
                    </Tr>
                    {isAdmin && !archived && expandedId === t.id && (
                      <tr>
                        <td colSpan={COLS} className="p-0">
                          <RosterPanel training={t} municipalities={municipalities} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                )
              })}
            </tbody>
          </Table>
        )}
      </PageBody>

      {isAdmin && (
        <Modal
          open={modalOpen}
          onClose={() => setModalOpen(false)}
          title={editing ? `Edit ${editing.title}` : 'New Training'}
          size="xl"
        >
          {modalOpen && (
            <TrainingForm
              key={editing?.id ?? 'new'}
              training={editing}
              catalog={catalog}
              onSaved={async () => {
                setModalOpen(false)
                await load()
              }}
              onCancel={() => setModalOpen(false)}
            />
          )}
        </Modal>
      )}
    </>
  )
}
