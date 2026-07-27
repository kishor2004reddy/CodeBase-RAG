import { useEffect, useState } from 'react'
import type { IngestStatus } from '../App'
import { checkHealth } from '../api/client'

interface Props {
  status: IngestStatus
  message: string
  activeRepoId: string | null
  stats: { files: number; symbols: number; chunks: number } | null
}

const colors: Record<IngestStatus, string> = {
  idle:    'var(--color-muted)',
  loading: 'var(--color-primary)',
  done:    'var(--color-success)',
  error:   'var(--color-error)',
}

export default function StatusBar({ status, message, activeRepoId, stats }: Props) {
  const [backendHealthy, setBackendHealthy] = useState<boolean | null>(null)

  useEffect(() => {
    checkHealth()
      .then(() => setBackendHealthy(true))
      .catch(() => setBackendHealthy(false))
  }, [])

  return (
    <div style={{
      padding: '8px 24px',
      background: 'var(--color-bg)',
      borderBottom: '1px solid var(--color-border)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      fontSize: '12px',
    }}>
      {/* Status Message */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: colors[status] }}>
        {status === 'loading' && <span className="spinner">⏳</span>}
        {status === 'done' && <span>✅</span>}
        {status === 'error' && <span>❌</span>}
        <span>{message || 'Ready for query'}</span>
      </div>

      {/* Repository Stats */}
      {activeRepoId && stats && (
        <div style={{ display: 'flex', gap: '16px', color: 'var(--color-muted)' }}>
          <span>📂 <strong>{stats.files}</strong> files</span>
          <span>⚡ <strong>{stats.symbols}</strong> AST symbols</span>
          <span>📦 <strong>{stats.chunks}</strong> vector chunks</span>
        </div>
      )}

      {/* Backend indicator */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <span style={{
          width: '8px',
          height: '8px',
          borderRadius: '50%',
          background: backendHealthy === true ? 'var(--color-success)' : backendHealthy === false ? 'var(--color-error)' : 'var(--color-muted)'
        }} />
        <span style={{ color: 'var(--color-muted)' }}>
          {backendHealthy === true ? 'Backend Online' : backendHealthy === false ? 'Backend Offline' : 'Checking...'}
        </span>
      </div>
    </div>
  )
}
