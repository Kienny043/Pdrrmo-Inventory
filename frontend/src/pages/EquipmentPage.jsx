import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiGet, apiPost, apiPatch, apiDelete } from '../lib/api'
import { downloadCsv } from '../lib/csv'
import { useAuth } from '../lib/auth'
import PageHeader, { PageBody } from '../components/PageHeader'
import { Table, THead, Th, Tr, Td } from '../components/Table'
import { Field, INPUT_CLASS, SearchInput } from '../components/Field'
import Button from '../components/Button'
import TextAction from '../components/TextAction'
import Badge from '../components/Badge'
import Modal from '../components/Modal'
import ErrorBanner from '../components/ErrorBanner'
import { LoadingSection } from '../components/Spinner'
import EmptyState from '../components/EmptyState'
import ItemHistoryModal from '../components/ItemHistoryModal'

const CONDITIONS = [
  ['NEW', 'New'],
  ['GOOD', 'Good'],
  ['FAIR', 'Fair'],
  ['NEEDS_REPAIR', 'Needs repair'],
  ['DAMAGED', 'Damaged'],
]

const CSV_COLUMNS = [
  { label: 'name', key: 'name' },
  { label: 'brand', key: 'brand' },
  { label: 'category', get: (r) => r.category_name },
  { label: 'quantity', key: 'quantity' },
  { label: 'unit', key: 'unit' },
  { label: 'condition', key: 'condition' },
  { label: 'holder', get: (r) => r.memorandum_receipt_name || '' },
  { label: 'date_acquired', key: 'date_acquired' },
  { label: 'remarks', key: 'remarks' },
]

function ItemForm({ item, categories, staff, onSaved, onCancel }) {
  const editing = !!item
  const [values, setValues] = useState(() => ({
    category: item?.category ? String(item.category) : '',
    name: item?.name ?? '',
    brand: item?.brand ?? '',
    description: item?.description ?? '',
    remarks: item?.remarks ?? '',
    quantity: item?.quantity != null ? String(item.quantity) : '1',
    unit: item?.unit ?? '',
    condition: item?.condition ?? 'GOOD',
    memorandum_receipt: item?.memorandum_receipt ? String(item.memorandum_receipt) : '',
    date_acquired: item?.date_acquired ?? '',
  }))
  const [file, setFile] = useState(null)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const set = (k) => (e) => setValues((v) => ({ ...v, [k]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      // Scalars + FKs as JSON (a multipart null on the nullable holder FK is
      // rejected); the image, if any, follows as a FormData PATCH.
      const payload = {
        category: Number(values.category),
        name: values.name,
        brand: values.brand,
        description: values.description,
        remarks: values.remarks,
        unit: values.unit,
        condition: values.condition,
        date_acquired: values.date_acquired || null,
        memorandum_receipt: values.memorandum_receipt ? Number(values.memorandum_receipt) : null,
      }
      if (!editing) payload.quantity = Number(values.quantity)
      const saved = editing
        ? await apiPatch(`/api/items/${item.id}/`, payload)
        : await apiPost('/api/items/', payload)
      if (file) {
        const fd = new FormData()
        fd.append('image', file)
        await apiPatch(`/api/items/${saved.id}/`, fd)
      }
      onSaved()
    } catch (err) {
      setError(err.message)
      setSubmitting(false)
    }
  }

  return (
    <form className="flex flex-col gap-4" onSubmit={submit}>
      {error && <ErrorBanner>{error}</ErrorBanner>}
      <Field label="Category" required>
        <select className={INPUT_CLASS} value={values.category} onChange={set('category')} required>
          <option value="">— select —</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Name" required>
        <input className={INPUT_CLASS} value={values.name} onChange={set('name')} required />
      </Field>
      <div className="grid grid-cols-2 gap-4">
        <Field label="Brand">
          <input className={INPUT_CLASS} value={values.brand} onChange={set('brand')} />
        </Field>
        <Field label="Unit">
          <input className={INPUT_CLASS} value={values.unit} onChange={set('unit')} placeholder="unit / set / box" />
        </Field>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <Field label="Quantity">
          <input
            type="number"
            min="0"
            className={INPUT_CLASS}
            value={values.quantity}
            onChange={set('quantity')}
            disabled={editing}
          />
        </Field>
        <Field label="Condition">
          <select className={INPUT_CLASS} value={values.condition} onChange={set('condition')}>
            {CONDITIONS.map(([v, label]) => (
              <option key={v} value={v}>
                {label}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <Field label="Holder">
        <select
          className={INPUT_CLASS}
          value={values.memorandum_receipt}
          onChange={set('memorandum_receipt')}
        >
          <option value="">— none —</option>
          {staff.map((s) => (
            <option key={s.id} value={s.id}>
              {s.full_name}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Date acquired">
        <input type="date" className={INPUT_CLASS} value={values.date_acquired} onChange={set('date_acquired')} />
      </Field>
      <Field label="Description">
        <textarea className={INPUT_CLASS} rows={2} value={values.description} onChange={set('description')} />
      </Field>
      <Field label="Remarks">
        <textarea className={INPUT_CLASS} rows={2} value={values.remarks} onChange={set('remarks')} />
      </Field>
      <Field label="Image">
        <input type="file" accept="image/*" className="text-sm" onChange={(e) => setFile(e.target.files[0] || null)} />
      </Field>
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

export default function EquipmentPage() {
  const { user } = useAuth()
  const canEdit = !!user?.is_admin

  const [items, setItems] = useState([])
  const [categories, setCategories] = useState([])
  const [staff, setStaff] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [catFilter, setCatFilter] = useState('')
  const [search, setSearch] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [historyItem, setHistoryItem] = useState(null)

  const load = useCallback(async () => {
    try {
      const jobs = [apiGet('/api/items/')]
      if (canEdit) jobs.push(apiGet('/api/categories/'), apiGet('/api/staff/'))
      const [it, cats, stf] = await Promise.all(jobs)
      setItems(it)
      setCategories(cats || [])
      setStaff(stf || [])
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [canEdit])

  useEffect(() => {
    load()
  }, [load])

  // ADMIN: filter options are categories (value = id). STAFF: derived from
  // the items' category_name (value = name) — /api/categories/ is ADMIN-only.
  const filterOptions = useMemo(() => {
    if (canEdit) return categories.map((c) => ({ value: String(c.id), label: c.name }))
    const seen = new Set()
    items.forEach((it) => it.category_name && seen.add(it.category_name))
    return [...seen].sort().map((n) => ({ value: n, label: n }))
  }, [canEdit, categories, items])

  const visibleRows = useMemo(() => {
    const q = search.trim().toLowerCase()
    return items.filter((it) => {
      const key = canEdit ? String(it.category) : it.category_name || ''
      if (catFilter && key !== catFilter) return false
      if (q && !`${it.name || ''} ${it.brand || ''}`.toLowerCase().includes(q)) return false
      return true
    })
  }, [items, search, catFilter, canEdit])

  const archive = async (it) => {
    setError('')
    try {
      await apiDelete(`/api/items/${it.id}/`)
      setItems((rs) => rs.filter((r) => r.id !== it.id))
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <>
      <PageHeader
        title="Equipment Dashboard"
        subtitle={loading ? '' : `${visibleRows.length} of ${items.length} items`}
        actions={
          <>
            <Button variant="secondary" onClick={() => downloadCsv('equipment.csv', visibleRows, CSV_COLUMNS)}>
              Export CSV
            </Button>
            {canEdit && (
              <Button
                onClick={() => {
                  setEditing(null)
                  setModalOpen(true)
                }}
              >
                + New Item
              </Button>
            )}
          </>
        }
      />
      <PageBody>
        {error && (
          <div className="mb-4">
            <ErrorBanner>{error}</ErrorBanner>
          </div>
        )}

        <div className="flex flex-wrap items-center gap-3 mb-4">
          <SearchInput
            placeholder="name or brand"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <div className="w-56">
            <select
              className={INPUT_CLASS}
              value={catFilter}
              onChange={(e) => setCatFilter(e.target.value)}
            >
              <option value="">All categories</option>
              {filterOptions.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {loading ? (
          <LoadingSection />
        ) : visibleRows.length === 0 ? (
          <EmptyState>No equipment matches.</EmptyState>
        ) : (
          <Table>
            <THead>
              <Th>Name</Th>
              <Th>Brand</Th>
              <Th>Category</Th>
              <Th>Qty</Th>
              <Th>Unit</Th>
              <Th>Condition</Th>
              <Th>Holder</Th>
              <Th>Remarks</Th>
              <Th>Acquired</Th>
              {canEdit && <Th className="w-44" />}
            </THead>
            <tbody>
              {visibleRows.map((it) => (
                <Tr key={it.id}>
                  <Td>{it.name}</Td>
                  <Td variant="muted">{it.brand || '—'}</Td>
                  <Td variant="muted">{it.category_name}</Td>
                  <Td>{it.quantity}</Td>
                  <Td variant="muted">{it.unit || '—'}</Td>
                  <Td variant="plain">
                    <Badge value={it.condition} />
                  </Td>
                  <Td variant="muted">{it.memorandum_receipt_name || '—'}</Td>
                  <Td variant="muted">{it.remarks || '—'}</Td>
                  <Td variant="muted">{it.date_acquired || '—'}</Td>
                  {canEdit && (
                    <Td variant="plain">
                      <div className="flex gap-3">
                        <TextAction
                          tone="muted"
                          onClick={() => {
                            setEditing(it)
                            setModalOpen(true)
                          }}
                        >
                          Edit
                        </TextAction>
                        <TextAction tone="navy" onClick={() => setHistoryItem(it)}>
                          History
                        </TextAction>
                        <TextAction
                          tone="red"
                          confirm={`Archive “${it.name}”? It moves to the Archived page.`}
                          onClick={() => archive(it)}
                        >
                          Archive
                        </TextAction>
                      </div>
                    </Td>
                  )}
                </Tr>
              ))}
            </tbody>
          </Table>
        )}
      </PageBody>

      {canEdit && (
        <Modal
          open={modalOpen}
          onClose={() => setModalOpen(false)}
          title={editing ? `Edit ${editing.name}` : 'New Item'}
          size="xl"
        >
          {modalOpen && (
            <ItemForm
              key={editing?.id ?? 'new'}
              item={editing}
              categories={categories}
              staff={staff}
              onSaved={async () => {
                setModalOpen(false)
                await load()
              }}
              onCancel={() => setModalOpen(false)}
            />
          )}
        </Modal>
      )}

      {canEdit && (
        <ItemHistoryModal item={historyItem} open={!!historyItem} onClose={() => setHistoryItem(null)} />
      )}
    </>
  )
}
