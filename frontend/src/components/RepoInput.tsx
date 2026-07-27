import { useState } from 'react'
import type { IngestStatus } from '../App'
import { ingestRepo } from '../api/client'

interface Props {
  onStatusChange: (status: IngestStatus, message: string) => void
}

export default function RepoInput({ onStatusChange }: Props) {
  const [repoUrl, setRepoUrl] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!repoUrl.trim()) return

    setLoading(true)
    onStatusChange('loading', 'Starting ingestion...')

    try {
      await ingestRepo(repoUrl.trim(), onStatusChange)
    } catch (err) {
      onStatusChange('error', 'Ingestion failed. Check the backend logs.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      padding: '16px 24px',
      borderBottom: '1px solid var(--color-border)',
      background: 'var(--color-surface)',
    }}>
      <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '10px' }}>
        <input
          type="url"
          placeholder="https://github.com/owner/repo"
          value={repoUrl}
          onChange={e => setRepoUrl(e.target.value)}
          disabled={loading}
          style={{ flex: 1 }}
        />
        <button
          type="submit"
          className="btn-primary"
          disabled={loading || !repoUrl.trim()}
        >
          {loading ? 'Indexing...' : 'Index Repo'}
        </button>
      </form>
    </div>
  )
}
