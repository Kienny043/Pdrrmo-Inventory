import { useCallback, useEffect, useState } from 'react'
import { apiGet, apiPost, apiDelete } from '../lib/api'
import { useAuth } from '../lib/auth'
import PageHeader, { PageBody } from '../components/PageHeader'
import { Table, THead, Th, Tr, Td } from '../components/Table'
import Tabs from '../components/Tabs'
import TextAction from '../components/TextAction'
import ErrorBanner from '../components/ErrorBanner'
import { LoadingSection } from '../components/Spinner'
import EmptyState from '../components/EmptyState'
import ItemHistoryModal from '../components/ItemHistoryModal'
import TrainingHistoryModal from '../components/TrainingHistoryModal'

const fdate = (v) => (v ? String(v).slice(0, 10) : '—')

// One config per tab — no per-tab logic. Every archivable resource exposes
// the same <base>/<id>/restore/ and <base>/<id>/permanent-delete/ shape.
const TABS = [
  {
    key: 'items',
    label: 'Items',
    url: '/api/items/archived/',
    base: '/api/items/',
    history: 'item',
    deleteWarn: 'Its stock-movement and holder-log history will be permanently deleted too.',
    cols: [
      { h: 'Name', f: 'name' },
      { h: 'Brand', f: 'brand' },
      { h: 'Category', f: 'category_name' },
      { h: 'Qty', f: 'quantity' },
      { h: 'Condition', f: 'condition' },
      { h: 'Archived', f: 'archived_at', fmt: fdate },
      { h: 'Archived by', f: 'archived_by' },
    ],
  },
  {
    key: 'staff',
    label: 'Staff',
    url: '/api/staff/archived/',
    base: '/api/staff/',
    cols: [
      { h: 'Name', f: 'full_name' },
      { h: 'Position', f: 'position' },
      { h: 'Department', f: 'department' },
      { h: 'Status', f: 'status' },
      { h: 'Archived', f: 'archived_at', fmt: fdate },
      { h: 'Archived by', f: 'archived_by' },
    ],
  },
  {
    key: 'trainings',
    label: 'Trainings',
    url: '/api/trainings/archived/',
    base: '/api/trainings/',
    history: 'training',
    deleteWarn: 'Its registrations, attendance, and roster will be permanently deleted too.',
    cols: [
      { h: 'Title', f: 'title' },
      { h: 'Start', f: 'date_start' },
      { h: 'Status', f: 'status' },
      { h: 'Matrix training', f: 'matrix_training_label' },
      { h: 'Archived', f: 'archived_at', fmt: fdate },
      { h: 'Archived by', f: 'archived_by' },
    ],
  },
  {
    key: 'personnel',
    label: 'Personnel',
    url: '/api/personnel/?archived=true',
    base: '/api/personnel/',
    deleteWarn: 'Its training-matrix records will be permanently deleted too.',
    cols: [
      { h: 'Name', f: 'name' },
      { h: 'Designation', f: 'designation' },
      { h: 'Municipality', f: 'municipality' },
      { h: 'District', f: 'district' },
      { h: 'Archived', f: 'archived_at', fmt: fdate },
      { h: 'Archived by', f: 'archived_by' },
    ],
  },
]

const labelOf = (r) => r.name || r.title || r.full_name || `#${r.id}`
const cell = (r, c) => {
  const v = r[c.f]
  if (c.fmt) return c.fmt(v)
  return v == null || v === '' ? '—' : String(v)
}

export default function ArchivedPage() {
  const { user } = useAuth()
  const canDelete = !!user?.can_permanently_delete

  const [activeKey, setActiveKey] = useState('items')
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [historyRow, setHistoryRow] = useState(null) // row whose History modal is open

  const tab = TABS.find((t) => t.key === activeKey)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setRows((await apiGet(tab.url)) || [])
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [tab.url])

  useEffect(() => {
    load()
  }, [load])

  const restore = async (r) => {
    setError('')
    try {
      await apiPost(`${tab.base}${r.id}/restore/`)
      setRows((rs) => rs.filter((x) => x.id !== r.id))
    } catch (e) {
      setError(`Restore failed: ${e.message}`)
    }
  }

  const permaDelete = async (r) => {
    setError('')
    try {
      await apiDelete(`${tab.base}${r.id}/permanent-delete/`)
      setRows((rs) => rs.filter((x) => x.id !== r.id))
    } catch (e) {
      setError(`Delete failed: ${e.message}`)
    }
  }

  return (
    <>
      <PageHeader
        title="Archived Records"
        subtitle={loading ? '' : `${rows.length} archived ${tab.label.toLowerCase()}`}
      />
      <Tabs
        tabs={TABS.map((t) => ({ key: t.key, label: t.label }))}
        active={activeKey}
        onChange={(k) => {
          setActiveKey(k)
          setHistoryRow(null)
        }}
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
          <EmptyState>Nothing archived in this tab.</EmptyState>
        ) : (
          <Table>
            <THead>
              {tab.cols.map((c) => (
                <Th key={c.h}>{c.h}</Th>
              ))}
              <Th className="w-56" />
            </THead>
            <tbody>
              {rows.map((r) => (
                <Tr key={r.id}>
                  {tab.cols.map((c, i) => (
                    <Td key={c.h} variant={i === 0 ? 'strong' : 'muted'}>
                      {cell(r, c)}
                    </Td>
                  ))}
                  <Td variant="plain">
                    <div className="flex gap-3">
                      {tab.history && (
                        <TextAction tone="navy" onClick={() => setHistoryRow(r)}>
                          History
                        </TextAction>
                      )}
                      <TextAction tone="green" onClick={() => restore(r)}>
                        Restore
                      </TextAction>
                      {canDelete && (
                        <TextAction
                          tone="red"
                          confirm={`Permanently delete "${labelOf(r)}"? This cannot be undone.${
                            tab.deleteWarn ? ' ' + tab.deleteWarn : ''
                          }`}
                          onClick={() => permaDelete(r)}
                        >
                          Delete permanently
                        </TextAction>
                      )}
                    </div>
                  </Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        )}
      </PageBody>

      <ItemHistoryModal
        item={tab.history === 'item' ? historyRow : null}
        open={tab.history === 'item' && !!historyRow}
        onClose={() => setHistoryRow(null)}
      />
      <TrainingHistoryModal
        training={tab.history === 'training' ? historyRow : null}
        open={tab.history === 'training' && !!historyRow}
        onClose={() => setHistoryRow(null)}
      />
    </>
  )
}
