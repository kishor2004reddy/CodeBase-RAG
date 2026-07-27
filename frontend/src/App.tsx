import RepoInput from './components/RepoInput'
import ChatPanel from './components/ChatPanel'
import StatusBar from './components/StatusBar'
import { useState } from 'react'

export type IngestStatus = 'idle' | 'loading' | 'done' | 'error'

function App() {
  const [ingestStatus, setIngestStatus] = useState<IngestStatus>('idle')
  const [statusMessage, setStatusMessage] = useState('')

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      {/* Header */}
      <header style={{
        padding: '14px 24px',
        borderBottom: '1px solid var(--color-border)',
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        background: 'var(--color-surface)',
      }}>
        <span style={{ fontSize: '20px' }}>🔍</span>
        <h1 style={{ fontSize: '17px', fontWeight: 600, color: 'var(--color-text)' }}>
          CodeGraphRAG
        </h1>
        <span style={{ fontSize: '12px', color: 'var(--color-muted)', marginLeft: '4px' }}>
          Ask anything about your codebase
        </span>
      </header>

      {/* Repo Input */}
      <RepoInput
        onStatusChange={(status, message) => {
          setIngestStatus(status)
          setStatusMessage(message)
        }}
      />

      {/* Status Bar */}
      {ingestStatus !== 'idle' && (
        <StatusBar status={ingestStatus} message={statusMessage} />
      )}

      {/* Chat Panel */}
      <ChatPanel enabled={ingestStatus === 'done'} />
    </div>
  )
}

export default App
