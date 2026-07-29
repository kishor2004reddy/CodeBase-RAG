import { useState } from 'react'
import { GitBranch, FileArchive, FolderPlus, X, Loader2, XCircle } from 'lucide-react'
import { ingestGithubRepo, ingestZipRepo } from '../api/client'

interface Props {
  onIngestSuccess: (repoId: string) => void
  // Only provided when there's an existing chat to fall back to —
  // omitted on first launch when a repo must be indexed to proceed.
  onCancel?: () => void
}

// This component is unmounted/remounted each time it's shown (App.tsx swaps
// it in/out of the tree rather than just hiding it), so this local state
// always starts fresh — no leftover results from a previous ingestion.
export default function RepoInput({ onIngestSuccess, onCancel }: Props) {
  const [tab, setTab] = useState<'github' | 'zip'>('github')
  const [repoUrl, setRepoUrl] = useState('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleGithubSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!repoUrl.trim() || loading) return

    setLoading(true)
    setError(null)

    try {
      const result = await ingestGithubRepo(repoUrl.trim())
      onIngestSuccess(result.repo_id)
    } catch (err: any) {
      setError(err.message || 'Ingestion failed.')
    } finally {
      setLoading(false)
    }
  }

  const handleZipSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedFile || loading) return

    setLoading(true)
    setError(null)

    try {
      const result = await ingestZipRepo(selectedFile)
      onIngestSuccess(result.repo_id)
    } catch (err: any) {
      setError(err.message || 'ZIP ingestion failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="repo-input-container">
      {/* Header — explains that a repo must be indexed to start this chat */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '7px',
          fontSize: '13px',
          fontWeight: 600,
          color: 'var(--color-text)',
        }}>
          <FolderPlus size={15} color="var(--color-primary)" />
          Index a repository to start this chat
        </div>
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="btn-ghost"
            style={{ fontSize: '12px', padding: '3px 9px', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
          >
            <X size={12} /> Cancel
          </button>
        )}
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
        <button
          type="button"
          className={tab === 'github' ? 'btn-tab active' : 'btn-tab'}
          onClick={() => setTab('github')}
          disabled={loading}
          style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
        >
          <GitBranch size={14} /> GitHub Repository
        </button>
        <button
          type="button"
          className={tab === 'zip' ? 'btn-tab active' : 'btn-tab'}
          onClick={() => setTab('zip')}
          disabled={loading}
          style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
        >
          <FileArchive size={14} /> ZIP File Upload
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

      {/* Live feedback for the ingestion currently in progress — scoped to
          this attempt only, never shows results from a previous chat. */}
      {loading && (
        <div style={{
          marginTop: '12px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          fontSize: '12px',
          color: 'var(--color-primary)',
        }}>
          <Loader2 size={13} className="spinner" />
          {tab === 'github' ? 'Cloning repository & parsing AST\u2026' : 'Uploading ZIP & parsing AST\u2026'}
        </div>
      )}

      {error && (
        <div style={{
          marginTop: '12px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '10px 14px',
          background: 'rgba(248, 113, 113, 0.1)',
          border: '1px solid var(--color-error)',
          color: 'var(--color-error)',
          borderRadius: 'var(--radius-sm)',
          fontSize: '12px',
        }}>
          <XCircle size={14} /> {error}
        </div>
      )}
    </div>
  )
}
