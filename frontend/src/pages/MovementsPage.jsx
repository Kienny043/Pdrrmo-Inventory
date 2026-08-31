import { useCallback, useEffect, useState } from 'react'
import { apiGet, apiPost } from '../lib/api'
import PageHeader, { PageBody } from '../components/PageHeader'
import { Table, THead, Th, Tr, Td } from '../components/Table'
import { Field, INPUT_CLASS } from '../components/Field'
import Button from '../components/Button'
import Card from '../components/Card'
import Badge from '../components/Badge'
import ErrorBanner from '../components/ErrorBanner'
import { LoadingSection } from '../components/Spinner'
import EmptyState from '../components/EmptyState'

export default function MovementsPage() {
  const [items, setItems] = useState([])
  const [movements, setMovements] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [formError, setFormError] = useState('')
  const [itemFilter, setItemFilter] = useState('')

  const [fItem, setFItem] = useState('')
  const [fType, setFType] = useState('IN')
  const [fQty, setFQty] = useState('1')
  const [fNote, setFNote] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const loadLog = useCallback(async (filter) => {
    const q = filter ? `?item=${filter}` : ''
    setMovements(await apiGet(`/api/movements/${q}`))
  }, [])

  const load = useCallback(async () => {
    try {
      const [it] = await Promise.all([apiGet('/api/items/'), loadLog(itemFilter)])
      setItems(it)
      if (!fItem && it.length) setFItem(String(it[0].id))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadLog])

  useEffect(() => {
    load()
  }, [load])

  const onFilterChange = async (v) => {
    setItemFilter(v)
    try {
      await loadLog(v)
    } catch (e) {
      setError(e.message)
    }
  }

  const record = async (e) => {
    e.preventDefault()
    setFormError('')
    setSubmitting(true)
    try {
      await apiPost('/api/movements/add/', {
        item: Number(fItem),
        movement_type: fType,
        quantity: Number(fQty),
        note: fNote,
      })
      setFQty('1')
      setFNote('')
      // refresh on-hand numbers + the log
      const it = await apiGet('/api/items/')
      setItems(it)
      await loadLog(itemFilter)
    } catch (err) {
      // insufficient stock (400) and any other error land here — show it on
      // the form persistently, not as a transient toast.
      setFormError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  const onHand = (id) => items.find((i) => String(i.id) === String(id))?.quantity

  return (
    <>
      <PageHeader title="Stock Movements" subtitle={loading ? '' : `${movements.length} recorded`} />
      <PageBody>
        {error && (
          <div className="mb-4">
            <ErrorBanner>{error}</ErrorBanner>
          </div>
        )}

        <Card className="p-5 mb-6">
          <form className="flex flex-col gap-4" onSubmit={record}>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Field label="Item">
              <select className={INPUT_CLASS} value={fItem} onChange={(e) => setFItem(e.target.value)}>
                {items.map((i) => (
                  <option key={i.id} value={i.id}>
                    {i.name} (on hand: {i.quantity})
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Type">
              <select className={INPUT_CLASS} value={fType} onChange={(e) => setFType(e.target.value)}>
                <option value="IN">Stock in</option>
                <option value="OUT">Stock out</option>
              </select>
            </Field>
            <Field label="Quantity">
              <input
                type="number"
                min="1"
                className={INPUT_CLASS}
                value={fQty}
                onChange={(e) => setFQty(e.target.value)}
                required
              />
            </Field>
            <Field label="Note">
              <input className={INPUT_CLASS} value={fNote} onChange={(e) => setFNote(e.target.value)} />
            </Field>
          </div>
          {formError && <ErrorBanner>{formError}</ErrorBanner>}
          <div className="flex items-center gap-3">
            <Button type="submit" disabled={submitting || !fItem}>
              {submitting ? 'Recording…' : 'Record movement'}
            </Button>
            {fItem && (
              <span className="text-xs text-pd-text-secondary">
                {items.find((i) => String(i.id) === fItem)?.name} — on hand {onHand(fItem)}
              </span>
            )}
          </div>
          </form>
        </Card>

        <div className="flex items-center gap-3 mb-4">
          <label className="text-xs text-pd-text-secondary">Filter by item</label>
          <div className="w-56">
            <select
              className={INPUT_CLASS}
              value={itemFilter}
              onChange={(e) => onFilterChange(e.target.value)}
            >
              <option value="">All items</option>
              {items.map((i) => (
                <option key={i.id} value={i.id}>
                  {i.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        {loading ? (
          <LoadingSection />
        ) : movements.length === 0 ? (
          <EmptyState>No movements recorded.</EmptyState>
        ) : (
          <Table>
            <THead>
              <Th>When</Th>
              <Th>Item</Th>
              <Th>Type</Th>
              <Th>Qty</Th>
              <Th>Note</Th>
              <Th>By</Th>
            </THead>
            <tbody>
              {movements.map((m) => (
                <Tr key={m.id}>
                  <Td variant="muted">{String(m.created_at).slice(0, 10)}</Td>
                  <Td>{m.item_name}</Td>
                  <Td variant="plain">
                    <Badge value={m.movement_type} />
                  </Td>
                  <Td>{m.quantity}</Td>
                  <Td variant="muted">{m.note || '—'}</Td>
                  <Td variant="muted">{m.performed_by || '—'}</Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        )}
      </PageBody>
    </>
  )
}
