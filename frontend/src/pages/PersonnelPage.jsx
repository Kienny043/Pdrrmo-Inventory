import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { apiGet, apiPost, apiPatch, apiDelete } from '../lib/api'
import PageHeader, { PageBody } from '../components/PageHeader'
import { Field, INPUT_CLASS } from '../components/Field'
import Button from '../components/Button'
import TextAction from '../components/TextAction'
import Modal from '../components/Modal'
import ErrorBanner from '../components/ErrorBanner'
import { LoadingSection } from '../components/Spinner'
import './PersonnelMatrix.css'

const YEAR_MIN = 2000
const YEAR_MAX = 2035

// "Basic Incident Command System Level 1" -> that; "Rapid Damage … (RDANA)" -> "RDANA"
function abbr(label) {
  const m = label.match(/\(([^)]+)\)\s*$/)
  return m ? m[1] : label
}

function flash(el, kind) {
  if (!el) return
  const cls = kind === 'ok' ? 'matrix-flash-ok' : 'matrix-flash-err'
  el.classList.remove('matrix-flash-ok', 'matrix-flash-err')
  // reflow so the animation restarts
  void el.offsetWidth
  el.classList.add(cls)
  setTimeout(() => el.classList.remove(cls), 600)
}

// --------------------------------------------------------------------------
// new-personnel modal
// --------------------------------------------------------------------------

function NewPersonnelForm({ munis, defaultMunicipality, onSaved, onCancel }) {
  const [v, setV] = useState({
    name: '',
    designation: '',
    municipality: defaultMunicipality || '',
    employment_status: '',
    org_affiliation: 'EMPLOYEE',
    other_drr_training: '',
  })
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const set = (k) => (e) => setV((s) => ({ ...s, [k]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await apiPost('/api/personnel/', v)
      onSaved(v.municipality)
    } catch (err) {
      setError(err.message)
      setSubmitting(false)
    }
  }

  return (
    <form className="flex flex-col gap-4" onSubmit={submit}>
      {error && <ErrorBanner>{error}</ErrorBanner>}
      <Field label="Name" required>
        <input className={INPUT_CLASS} value={v.name} onChange={set('name')} required autoComplete="off" />
      </Field>
      <Field label="Designation">
        <input className={INPUT_CLASS} value={v.designation} onChange={set('designation')} autoComplete="off" />
      </Field>
      <Field label="Municipality" required>
        <select className={INPUT_CLASS} value={v.municipality} onChange={set('municipality')} required>
          <option value="">— select —</option>
          {munis.map((m) => (
            <option key={m.name} value={m.name}>
              {m.name}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Employment status">
        <input className={INPUT_CLASS} value={v.employment_status} onChange={set('employment_status')} autoComplete="off" />
      </Field>
      <Field label="Org affiliation">
        <select className={INPUT_CLASS} value={v.org_affiliation} onChange={set('org_affiliation')}>
          <option value="EMPLOYEE">Employee</option>
          <option value="VOLUNTEER">Volunteer</option>
        </select>
      </Field>
      <Field label="Other DRR training">
        <textarea className={INPUT_CLASS} rows={2} value={v.other_drr_training} onChange={set('other_drr_training')} />
      </Field>
      <div className="flex justify-end gap-3 mt-2">
        <Button variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={submitting}>
          {submitting ? 'Creating…' : 'Create'}
        </Button>
      </div>
    </form>
  )
}

// --------------------------------------------------------------------------
// page
// --------------------------------------------------------------------------

export default function PersonnelPage() {
  const [catalog, setCatalog] = useState([])
  const [municipalities, setMunicipalities] = useState([])
  const [district, setDistrict] = useState('')
  const [municipality, setMunicipality] = useState('')
  const [view, setView] = useState('active')
  const [rows, setRows] = useState([])
  const [refLoaded, setRefLoaded] = useState(false)
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState({ text: '', kind: '' })
  const [modalOpen, setModalOpen] = useState(false)

  const archived = view === 'archived'
  const showMunicipality = !municipality

  // reference data (once). Default the district to the first one the API
  // returns (First District) so the matrix shows data on open instead of an
  // empty "pick a district" state.
  useEffect(() => {
    Promise.all([apiGet('/api/training-catalog/'), apiGet('/api/municipalities/')])
      .then(([cat, muni]) => {
        setCatalog(cat)
        setMunicipalities(muni)
        setDistrict((cur) => cur || muni[0]?.district || '')
        setRefLoaded(true)
      })
      .catch((e) => setStatus({ text: `Failed to load reference data: ${e.message}`, kind: 'err' }))
  }, [])

  const districts = useMemo(() => {
    const seen = []
    municipalities.forEach((m) => {
      if (!seen.includes(m.district)) seen.push(m.district)
    })
    return seen
  }, [municipalities])

  const munisInDistrict = useCallback(
    (d) => municipalities.filter((m) => m.district === d),
    [municipalities]
  )

  const managerial = useMemo(() => catalog.filter((c) => c.group === 'MANAGERIAL'), [catalog])
  const skills = useMemo(() => catalog.filter((c) => c.group === 'SKILLS'), [catalog])
  const trainingCols = useMemo(() => [...managerial, ...skills], [managerial, skills])

  const loadMatrix = useCallback(async () => {
    if (!district) {
      setRows([])
      return
    }
    setLoading(true)
    setStatus({ text: 'Loading…', kind: '' })
    try {
      const params = new URLSearchParams()
      if (municipality) params.set('municipality', municipality)
      else params.set('district', district)
      if (archived) params.set('archived', 'true')
      const data = await apiGet(`/api/personnel/?${params.toString()}`)
      setRows(data || [])
      setStatus({ text: '', kind: '' })
    } catch (e) {
      setStatus({ text: `Load failed: ${e.message}`, kind: 'err' })
    } finally {
      setLoading(false)
    }
  }, [district, municipality, archived])

  useEffect(() => {
    if (refLoaded) loadMatrix()
  }, [refLoaded, loadMatrix])

  // ---- inline mutations ----

  const savePersonnel = async (p, patch, control, field) => {
    control?.classList.add('matrix-cell-saving')
    try {
      const updated = await apiPatch(`/api/personnel/${p.id}/`, patch)
      setRows((rs) => rs.map((r) => (r.id === p.id ? { ...r, ...updated } : r)))
      control?.classList.remove('matrix-cell-saving')
      flash(control, 'ok')
      setStatus({ text: 'Saved', kind: 'ok' })
    } catch (e) {
      control?.classList.remove('matrix-cell-saving')
      flash(control, 'err')
      if (control && field && 'value' in control) control.value = p[field] == null ? '' : String(p[field])
      setStatus({ text: `Save failed: ${e.message}`, kind: 'err' })
    }
  }

  const saveCell = async (p, key, input) => {
    const raw = input.value.trim()
    const prev = input.dataset.current || ''
    if (raw === prev) return
    input.classList.add('matrix-cell-saving')
    try {
      let newVal = ''
      if (raw === '') {
        await apiPatch(`/api/personnel/${p.id}/training-record/${key}/`, { year_attained: null })
      } else {
        const rec = await apiPatch(`/api/personnel/${p.id}/training-record/${key}/`, {
          year_attained: Number(raw),
        })
        newVal = String(rec.year_attained)
      }
      input.classList.remove('matrix-cell-saving')
      input.value = newVal
      input.dataset.current = newVal
      setRows((rs) =>
        rs.map((r) => {
          if (r.id !== p.id) return r
          const recs = r.training_records.filter((x) => x.training_key !== key)
          if (newVal !== '') recs.push({ training_key: key, year_attained: Number(newVal) })
          return { ...r, training_records: recs }
        })
      )
      flash(input, 'ok')
      setStatus({ text: 'Saved', kind: 'ok' })
    } catch (e) {
      input.classList.remove('matrix-cell-saving')
      input.value = prev
      flash(input, 'err')
      setStatus({ text: `Cell save failed (${key}): ${e.message}`, kind: 'err' })
    }
  }

  const archivePerson = async (p) => {
    try {
      await apiDelete(`/api/personnel/${p.id}/`)
      setStatus({ text: 'Archived', kind: 'ok' })
      loadMatrix()
    } catch (e) {
      setStatus({ text: `Archive failed: ${e.message}`, kind: 'err' })
    }
  }
  const restorePerson = async (p) => {
    try {
      await apiPost(`/api/personnel/${p.id}/restore/`)
      setStatus({ text: 'Restored', kind: 'ok' })
      loadMatrix()
    } catch (e) {
      setStatus({ text: `Restore failed: ${e.message}`, kind: 'err' })
    }
  }

  // non-Name identity columns: Designation, Employment Status, Org Affiliation [, Municipality]
  const leadRest = 3 + (showMunicipality ? 1 : 0)

  return (
    <>
      <PageHeader
        title="Trained Personnel & Training Matrix"
        subtitle={
          !district
            ? 'Select a district'
            : `${rows.length} ${archived ? 'archived ' : ''}personnel · ${municipality || district}`
        }
      />
      <PageBody>
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <div className="w-52">
            <select
              className={INPUT_CLASS}
              value={district}
              onChange={(e) => {
                setDistrict(e.target.value)
                setMunicipality('')
              }}
            >
              <option value="">— select a district —</option>
              {districts.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </div>
          <div className="w-52">
            <select
              className={INPUT_CLASS}
              value={municipality}
              disabled={!district}
              onChange={(e) => setMunicipality(e.target.value)}
            >
              <option value="">All municipalities</option>
              {munisInDistrict(district).map((m) => (
                <option key={m.name} value={m.name}>
                  {m.name}
                </option>
              ))}
            </select>
          </div>
          <div className="w-36">
            <select className={INPUT_CLASS} value={view} onChange={(e) => setView(e.target.value)}>
              <option value="active">Active</option>
              <option value="archived">Archived</option>
            </select>
          </div>
          <Button disabled={!district} onClick={() => setModalOpen(true)}>
            + New Personnel
          </Button>
          {status.text && (
            <span
              className={`text-xs ${
                status.kind === 'err' ? 'text-pd-red' : status.kind === 'ok' ? 'text-pd-green' : 'text-pd-text-secondary'
              }`}
            >
              {status.text}
            </span>
          )}
        </div>

        {!refLoaded || (!district && loading) ? (
          <LoadingSection />
        ) : !district ? (
          <p className="text-center text-pd-text-secondary py-24">Select a district to load the matrix.</p>
        ) : loading ? (
          <LoadingSection />
        ) : rows.length === 0 ? (
          <p className="text-center text-pd-text-secondary py-24">
            {archived ? 'No archived personnel in this scope.' : 'No personnel in this scope yet — use “+ New Personnel”.'}
          </p>
        ) : (
          <div className="matrix-scroll">
            <table id="matrix-grid">
              <thead>
                {/* row 1 — group bands (two FULL rows, no rowspan) */}
                <tr className="band-row">
                  <th className="col-name corner" />
                  <th className="corner" colSpan={leadRest} />
                  <th className="band-managerial" colSpan={managerial.length}>
                    <span className="band-label">MANAGERIAL</span>
                  </th>
                  <th className="band-skills" colSpan={skills.length}>
                    <span className="band-label">SKILLS</span>
                  </th>
                  <th className="corner" />
                  <th className="corner row-actions" />
                </tr>
                {/* row 2 — every column label */}
                <tr className="label-row">
                  <th className="col-name">Name</th>
                  <th>Designation</th>
                  <th>Employment Status</th>
                  <th>Org Affiliation</th>
                  {showMunicipality && <th>Municipality</th>}
                  {trainingCols.map((c) => (
                    <th key={c.key} className="train-h" title={c.label}>
                      {abbr(c.label)}
                    </th>
                  ))}
                  <th>Other DRR Training</th>
                  <th className="row-actions" />
                </tr>
              </thead>
              <tbody>
                {rows.map((p) => (
                  <PersonRow
                    key={p.id}
                    p={p}
                    trainingCols={trainingCols}
                    showMunicipality={showMunicipality}
                    archived={archived}
                    onSaveIdentity={savePersonnel}
                    onSaveCell={saveCell}
                    onArchive={archivePerson}
                    onRestore={restorePerson}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </PageBody>

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title="New Personnel"
      >
        {modalOpen && (
          <NewPersonnelForm
            munis={munisInDistrict(district)}
            defaultMunicipality={municipality}
            onSaved={async (createdMuni) => {
              setModalOpen(false)
              // if a municipality filter is active and the new person isn't in it,
              // switch to it so the new row is visible
              if (municipality && createdMuni && createdMuni !== municipality) setMunicipality(createdMuni)
              else await loadMatrix()
            }}
            onCancel={() => setModalOpen(false)}
          />
        )}
      </Modal>
    </>
  )
}

// --------------------------------------------------------------------------
// one personnel row (uncontrolled inline inputs, blur-to-save)
// --------------------------------------------------------------------------

function PersonRow({ p, trainingCols, showMunicipality, archived, onSaveIdentity, onSaveCell, onArchive, onRestore }) {
  const byKey = useRef({})
  byKey.current = {}
  p.training_records.forEach((r) => {
    byKey.current[r.training_key] = r.year_attained
  })

  const idCell = (field, { extraClass = '', textarea = false } = {}) => {
    const cur = p[field] == null ? '' : String(p[field])
    const onBlur = (e) => {
      if (e.target.value !== cur) onSaveIdentity(p, { [field]: e.target.value }, e.target, field)
    }
    return (
      <td className={`id-cell ${extraClass}`}>
        {textarea ? (
          <textarea rows={1} defaultValue={cur} onBlur={onBlur} />
        ) : (
          <input type="text" defaultValue={cur} onBlur={onBlur} />
        )}
      </td>
    )
  }

  return (
    <tr data-person-id={p.id}>
      {/* Name — frozen column */}
      <td className="id-cell col-name">
        <input
          type="text"
          defaultValue={p.name || ''}
          onBlur={(e) => {
            if (e.target.value !== (p.name || '')) onSaveIdentity(p, { name: e.target.value }, e.target, 'name')
          }}
        />
      </td>
      {idCell('designation')}
      {idCell('employment_status')}
      <td className="id-cell">
        <select
          defaultValue={p.org_affiliation}
          onChange={(e) => onSaveIdentity(p, { org_affiliation: e.target.value }, e.target, 'org_affiliation')}
        >
          <option value="EMPLOYEE">Employee</option>
          <option value="VOLUNTEER">Volunteer</option>
        </select>
      </td>
      {showMunicipality && <td>{p.municipality}</td>}

      {trainingCols.map((c) => {
        const year = byKey.current[c.key]
        return (
          <td key={c.key} className="year-cell">
            <input
              type="number"
              min={YEAR_MIN}
              max={YEAR_MAX}
              step="1"
              className="year"
              placeholder="–"
              defaultValue={year != null ? String(year) : ''}
              data-current={year != null ? String(year) : ''}
              data-key={c.key}
              onBlur={(e) => onSaveCell(p, c.key, e.target)}
            />
          </td>
        )
      })}

      {idCell('other_drr_training', { extraClass: 'other', textarea: true })}

      <td className="row-actions">
        {archived ? (
          <TextAction tone="green" onClick={() => onRestore(p)}>
            Restore
          </TextAction>
        ) : (
          <TextAction tone="red" confirm={`Archive ${p.name}? They'll be hidden from the active matrix (not deleted).`} onClick={() => onArchive(p)}>
            Archive
          </TextAction>
        )}
      </td>
    </tr>
  )
}
