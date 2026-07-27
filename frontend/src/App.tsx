import { useState } from 'react'
import RepoInput from './components/RepoInput'
import ChatPanel from './components/ChatPanel'
import StatusBar from './components/StatusBar'
import GraphDrawer from './components/GraphDrawer'

export type IngestStatus = 'idle' | 'loading' | 'done' | 'error'

export interface RepoStats {
  files: number
  symbols: number
  chunks: number
}

function App() {
  const [ingestStatus, setIngestStatus] = useState<IngestStatus>('idle')
  const [statusMessage, setStatusMessage] = useState('')
  const [activeRepoId, setActiveRepoId] = useState<string | null>(null)
  const [repoStats, setRepoStats] = useState<RepoStats | null>(null)

  // Drawer state
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [drawerGraphCount, setDrawerGraphCount] = useState(0)
  const [drawerCitations, setDrawerCitations] = useState<string[]>([])
  const [drawerModelUsed, setDrawerModelUsed] = useState('')

  const handleIngestSuccess = (
    repoId: string,
    files: number,
    symbols: number,
    chunks: number
  ) => {
    setActiveRepoId(repoId)
    setRepoStats({ files, symbols, chunks })
  }

  const handleInspectGraph = (
    graphCount: number,
    citations: string[],
    modelUsed: string
  ) => {
    setDrawerGraphCount(graphCount)
    setDrawerCitations(citations)
    setDrawerModelUsed(modelUsed)
    setDrawerOpen(true)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: 'var(--color-bg)' }}>
      {/* Top Navigation Header */}
      <header style={{
        padding: '14px 24px',
        borderBottom: '1px solid var(--color-border)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: 'var(--color-surface)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '32px',
            height: '32px',
            borderRadius: 'var(--radius-sm)',
            background: 'var(--color-primary)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '18px',
          }}>
            🕸️
          </div>
          <div>
            <h1 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--color-text)', display: 'flex', alignItems: 'center', gap: '8px' }}>
              CodeGraphRAG
              <span className="badge-tech">Python + TS</span>
              <span className="badge-tech">Qdrant + Neo4j</span>
            </h1>
            <div style={{ fontSize: '12px', color: 'var(--color-muted)' }}>
              Structure-Aware Multi-Language Codebase Intelligence
            </div>
          </div>
        </div>

        {activeRepoId && (
          <div className="active-repo-badge">
            📌 Active Repo: <strong>{activeRepoId}</strong>
          </div>
        )}
      </header>

      {/* Repo Input */}
      <RepoInput
        onIngestSuccess={handleIngestSuccess}
        onStatusChange={(status, message) => {
          setIngestStatus(status)
          setStatusMessage(message)
        }}
      />

      {/* Status Bar */}
      <StatusBar
        status={ingestStatus}
        message={statusMessage}
        activeRepoId={activeRepoId}
        stats={repoStats}
      />

      {/* Main Interactive Chat Panel */}
      <ChatPanel
        repoId={activeRepoId}
        onInspectGraph={handleInspectGraph}
      />

      {/* Graph & Citation Inspection Drawer */}
      <GraphDrawer
        isOpen={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        graphCount={drawerGraphCount}
        citations={drawerCitations}
        modelUsed={drawerModelUsed}
      />
    </div>
  )
}

export default App
