// R2 stand-in for the 8 real pages (R3-R6). Renders the real layout
// chrome (header + body) so routing, the sidebar and the page shell are
// all verifiable now.
import PageHeader, { PageBody } from './PageHeader'
import EmptyState from './EmptyState'
import { useAuth } from '../lib/auth'

export default function PlaceholderPage({ title, step }) {
  const { user } = useAuth()
  return (
    <>
      <PageHeader title={title} subtitle={`Placeholder — real page lands in ${step}`} />
      <PageBody>
        <EmptyState>
          {title} content is not built yet. Signed in as{' '}
          <span className="font-semibold text-pd-text-primary">{user?.username}</span> (
          {user?.is_admin ? 'ADMIN' : 'STAFF'}).
        </EmptyState>
      </PageBody>
    </>
  )
}
