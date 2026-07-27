import { useState } from 'react'
import type { IngestStatus } from '../App'
import { ingestGithubRepo, ingestZipRepo } from '../api/client'

interface Props {
  onIngestSuccess: (repoId: string, files: number, symbols: number, chunks: number) => void
  onStatusChange: (status: IngestStatus, message: string) => void
}

export default function RepoInput({ onIngestSuccess, onStatusChange }: Props) {
  const [tab, setTab] = useState<'github' | 'zip'>('github')
  const [repoUrl, setRepoUrl] = useState('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)

  const handleGithubSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!repoUrl.trim() || loading) return

    setLoading(true)
    onStatusChange('loading', 'Cloning repository & parsing AST...')

    try {
      const result = await ingestGithubRepo(repoUrl.trim())
      onStatusChange('done', result.message)
      onIngestSuccess(
        result.repo_id,
        result.files_processed,
        result.symbols_extracted,
        result.chunks_created
      )
    } catch (err: any) {
      onStatusChange('error', err.message || 'Ingestion failed.')
    } finally {
      setLoading(false)
    }
  }

  const handleZipSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedFile || loading) return

    setLoading(true)
    onStatusChange('loading', 'Uploading ZIP & parsing AST...')

    try {
      const result = await ingestZipRepo(selectedFile)
      onStatusChange('done', result.message)
      onIngestSuccess(
        result.repo_id,
        result.files_processed,
        result.symbols_extracted,
        result.chunks_created
      )
    } catch (err: any) {
      onStatusChange('error', err.message || 'ZIP ingestion failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="repo-input-container">
      {/* Tabs */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
        <button
          type="button"
          className={tab === 'github' ? 'btn-tab active' : 'btn-tab'}
          onClick={() => setTab('github')}
          disabled={loading}
        >
          🐙 GitHub Repository
        </button>
        <button
          type="button"
          className={tab === 'zip' ? 'btn-tab active' : 'btn-tab'}
          onClick={() => setTab('zip')}
          disabled={loading}
        >
          📦 ZIP File Upload
        </button>
      </div>

      {/* GitHub Tab */}
      {tab === 'github' && (
        <form onSubmit={handleGithubSubmit} style={{ display: 'flex', gap: '10px' }}>
          <input
            type="url"
            placeholder="https://github.com/username/repository"
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
      )}

      {/* ZIP Tab */}
      {tab === 'zip' && (
        <form onSubmit={handleZipSubmit} style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <input
            type="file"
            accept=".zip"
            onChange={e => setSelectedFile(e.target.files?.[0] || null)}
            disabled={loading}
            style={{
              flex: 1,
              background: 'var(--color-surface)',
              padding: '6px 12px',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--color-border)',
              color: 'var(--color-text)',
            }}
          />
          <button
            type="submit"
            className="btn-primary"
            disabled={loading || !selectedFile}
          >
            {loading ? 'Indexing ZIP...' : 'Upload & Index ZIP'}
          </button>
        </form>
      )}
    </div>
  )
}
