import { useCallback, useEffect, useState } from 'react'
import { apiGet, apiPost, apiPatch, apiDelete } from '../lib/api'
import { useAuth } from '../lib/auth'
import PageHeader, { PageBody } from '../components/PageHeader'
import { Table, THead, Th, Tr, Td } from '../components/Table'
import { Field, INPUT_CLASS } from '../components/Field'
import Card from '../components/Card'
import Button from '../components/Button'
import TextAction from '../components/TextAction'
import Badge from '../components/Badge'
import ErrorBanner from '../components/ErrorBanner'
import { LoadingSection } from '../components/Spinner'
import EmptyState from '../components/EmptyState'

function decidedText(r) {
  if (!r.decided_by) return '—'
  return r.decided_by + (r.decided_at ? ` · ${String(r.decided_at).slice(0, 10)}` : '')
}

export default function RequestsPage() {
  const { user } = useAuth()
  const isAdmin = !!user?.is_admin
  const me = user?.username

  const [requests, setRequests] = useState([])
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [rowError, setRowError] = useState({}) // { [requestId]: message }

  const [fItem, setFItem] = useState('')
  const [fQty, setFQty] = useState('1')
  const [fNote, setFNote] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const load = useCallback(async () => {
    try {
      const [reqs, its] = await Promise.all([apiGet('/api/requests/'), apiGet('/api/items/')])
      setRequests(reqs)
      setItems(its)
      if (!fItem && its.length) setFItem(String(its[0].id))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await apiPost('/api/requests/', {
        item: Number(fItem),
        quantity: Number(fQty),
        note: fNote,
      })
      setFQty('1')
      setFNote('')
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  const decide = async (req, decision) => {
    setRowError((m) => ({ ...m, [req.id]: '' }))
    try {
      await apiPatch(`/api/requests/${req.id}/approve/`, { decision })
      await load()
    } catch (err) {
      // insufficient stock (400) / already-decided (409): show it on the row,
      // leave the request as it was.
      setRowError((m) => ({ ...m, [req.id]: err.message }))
    }
  }

  const withdraw = async (req) => {
    setRowError((m) => ({ ...m, [req.id]: '' }))
    try {
      await apiDelete(`/api/requests/${req.id}/withdraw/`)
      await load()
    } catch (err) {
      setRowError((m) => ({ ...m, [req.id]: err.message }))
    }
  }

  return (
    <>
      <PageHeader
        title="Equipment Requests"
        subtitle={loading ? '' : `${requests.length} request${requests.length === 1 ? '' : 's'}`}
      />
      <PageBody>
        {error && (
          <div className="mb-4">
            <ErrorBanner>{error}</ErrorBanner>
          </div>
        )}

        <Card className="p-5 mb-6">
          <form className="flex flex-col gap-4" onSubmit={submit}>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <Field label="Item">
                <select className={INPUT_CLASS} value={fItem} onChange={(e) => setFItem(e.target.value)}>
                  {items.map((i) => (
                    <option key={i.id} value={i.id}>
                      {i.name} (on hand: {i.quantity})
                    </option>
                  ))}
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
            <div>
              <Button type="submit" disabled={submitting || !fItem}>
                {submitting ? 'Submitting…' : 'Submit request'}
              </Button>
            </div>
          </form>
        </Card>

        {loading ? (
          <LoadingSection />
        ) : requests.length === 0 ? (
          <EmptyState>No requests yet.</EmptyState>
        ) : (
          <Table>
            <THead>
              <Th>Item</Th>
              <Th>Qty</Th>
              <Th>Status</Th>
              <Th>Note</Th>
              <Th>Requester</Th>
              <Th>Decided by</Th>
              <Th className="w-52" />
            </THead>
            <tbody>
              {requests.map((r) => (
                <Tr key={r.id}>
                  <Td>{r.item_name}</Td>
                  <Td>{r.quantity}</Td>
                  <Td variant="plain">
                    <Badge value={r.status} />
                  </Td>
                  <Td variant="muted">{r.note || '—'}</Td>
                  <Td variant="muted">{r.requested_by}</Td>
                  <Td variant="muted">{decidedText(r)}</Td>
                  <Td variant="plain">
                    {/* decided rows render no controls at all */}
                    {r.status === 'PENDING' && (
                      <div>
                        <div className="flex gap-3">
                          {isAdmin && (
                            <>
                              <TextAction tone="green" onClick={() => decide(r, 'APPROVED')}>
                                Approve
                              </TextAction>
                              <TextAction
                                tone="red"
                                confirm={`Reject this request for ${r.quantity}× ${r.item_name}?`}
                                onClick={() => decide(r, 'REJECTED')}
                              >
                                Reject
                              </TextAction>
                            </>
                          )}
                          {r.requested_by === me && (
                            <TextAction
                              tone="red"
                              confirm={`Withdraw your request for ${r.quantity}× ${r.item_name}?`}
                              onClick={() => withdraw(r)}
                            >
                              Withdraw
                            </TextAction>
                          )}
                        </div>
                        {rowError[r.id] && (
                          <p className="text-xs text-pd-red mt-1">{rowError[r.id]}</p>
                        )}
                      </div>
                    )}
                  </Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        )}
      </PageBody>
    </>
  )
}
