import { useCallback, useEffect, useState } from 'react'
import { apiGet, apiPost, apiPatch, apiDelete } from '../lib/api'
import PageHeader, { PageBody } from '../components/PageHeader'
import { Table, THead, Th, Tr, Td } from '../components/Table'
import { INPUT_CLASS } from '../components/Field'
import Button from '../components/Button'
import TextAction from '../components/TextAction'
import ErrorBanner from '../components/ErrorBanner'
import { LoadingSection } from '../components/Spinner'
import EmptyState from '../components/EmptyState'

export default function CategoriesPage() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [newName, setNewName] = useState('')
  const [newDesc, setNewDesc] = useState('')
  const [adding, setAdding] = useState(false)

  const load = useCallback(async () => {
    try {
      setRows(await apiGet('/api/categories/'))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const add = async () => {
    const name = newName.trim()
    if (!name) return
    setError('')
    setAdding(true)
    try {
      await apiPost('/api/categories/', { name, description: newDesc.trim() })
      setNewName('')
      setNewDesc('')
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setAdding(false)
    }
  }

  // Blur-to-save an inline cell edit, matching the current template behaviour.
  const saveCell = async (row, field, el) => {
    const next = el.value
    if (next === (row[field] ?? '')) return
    setError('')
    try {
      const updated = await apiPatch(`/api/categories/${row.id}/`, { [field]: next })
      setRows((rs) => rs.map((r) => (r.id === row.id ? updated : r)))
    } catch (e) {
      el.value = row[field] ?? '' // revert
      setError(e.message)
    }
  }

  const remove = async (row) => {
    setError('')
    try {
      await apiDelete(`/api/categories/${row.id}/`)
      setRows((rs) => rs.filter((r) => r.id !== row.id))
    } catch (e) {
      // 409 when the category still has items — surface the server message.
      setError(e.message)
    }
  }

  return (
    <>
      <PageHeader
        title="Equipment Categories"
        subtitle={loading ? '' : `${rows.length} categor${rows.length === 1 ? 'y' : 'ies'}`}
      />
      <PageBody>
        {error && (
          <div className="mb-4">
            <ErrorBanner>{error}</ErrorBanner>
          </div>
        )}

        {loading ? (
          <LoadingSection />
        ) : (
          <Table>
            <THead>
              <Th>Name</Th>
              <Th>Description</Th>
              <Th className="w-24">Items</Th>
              <Th className="w-24" />
            </THead>
            <tbody>
              <Tr>
                <Td variant="plain">
                  <input
                    className={INPUT_CLASS}
                    placeholder="New category name"
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && add()}
                  />
                </Td>
                <Td variant="plain">
                  <input
                    className={INPUT_CLASS}
                    placeholder="Description"
                    value={newDesc}
                    onChange={(e) => setNewDesc(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && add()}
                  />
                </Td>
                <Td variant="muted">—</Td>
                <Td variant="plain">
                  <Button onClick={add} disabled={adding || !newName.trim()}>
                    {adding ? 'Adding…' : 'Add'}
                  </Button>
                </Td>
              </Tr>

              {rows.map((row) => (
                <Tr key={row.id}>
                  <Td variant="plain">
                    <input
                      className={INPUT_CLASS}
                      defaultValue={row.name ?? ''}
                      onBlur={(e) => saveCell(row, 'name', e.target)}
                    />
                  </Td>
                  <Td variant="plain">
                    <input
                      className={INPUT_CLASS}
                      defaultValue={row.description ?? ''}
                      onBlur={(e) => saveCell(row, 'description', e.target)}
                    />
                  </Td>
                  <Td variant="muted">{row.item_count}</Td>
                  <Td variant="plain">
                    <TextAction
                      tone="red"
                      confirm={`Delete category “${row.name}”?`}
                      onClick={() => remove(row)}
                    >
                      Delete
                    </TextAction>
                  </Td>
                </Tr>
              ))}

              {rows.length === 0 && (
                <tr>
                  <td colSpan={4}>
                    <EmptyState>No categories yet.</EmptyState>
                  </td>
                </tr>
              )}
            </tbody>
          </Table>
        )}
      </PageBody>
    </>
  )
}
