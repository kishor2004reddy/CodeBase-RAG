/**
 * App.tsx
 * -------
 * Root layout: resizable sidebar (left) + main content area (right).
 *
 * Session management:
 *  - Sessions stored in localStorage (id, repoId, name, preview, createdAt)
 *  - Active session_id sent to backend for LangGraph Redis-backed memory
 *  - "New Chat" creates a new UUID session for the currently active repo
 *  - "Index New Repo" opens the repo ingestion panel
 */

import { useState, useCallback, useEffect } from 'react'
import Sidebar, { type Session } from './components/Sidebar'
import RepoInput from './components/RepoInput'
import ChatPanel from './components/ChatPanel'
import StatusBar from './components/StatusBar'
import GraphDrawer from './components/GraphDrawer'
import EvalDashboard from './components/EvalDashboard'

export type IngestStatus = 'idle' | 'loading' | 'done' | 'error'

export interface RepoStats {
  files: number
  symbols: number
  chunks: number
}

const SESSIONS_KEY = 'coderag:sessions'

function loadSessions(): Session[] {
  try {
    return JSON.parse(localStorage.getItem(SESSIONS_KEY) || '[]')
  } catch {
    return []
  }
}

function saveSessions(sessions: Session[]) {
  localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions))
}

function App() {
  const [ingestStatus, setIngestStatus] = useState<IngestStatus>('idle')
  const [statusMessage, setStatusMessage] = useState('')
  const [activeRepoId, setActiveRepoId] = useState<string | null>(null)
  const [repoStats, setRepoStats] = useState<RepoStats | null>(null)
  const [showRepoInput, setShowRepoInput] = useState(true)

  // Session state
  const [sessions, setSessions] = useState<Session[]>(loadSessions)
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)

  // Drawer & Modal state
  const [evalOpen, setEvalOpen] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [drawerGraphCount, setDrawerGraphCount] = useState(0)
  const [drawerCitations, setDrawerCitations] = useState<string[]>([])
  const [drawerModelUsed, setDrawerModelUsed] = useState('')

  // Persist sessions to localStorage whenever they change
  useEffect(() => {
    saveSessions(sessions)
  }, [sessions])

  const activeSession = sessions.find(s => s.id === activeSessionId) ?? null

  // ── Repo ingestion success ─────────────────────────────────────────
  const handleIngestSuccess = useCallback((
    repoId: string,
    files: number,
    symbols: number,
    chunks: number,
  ) => {
    setActiveRepoId(repoId)
    setRepoStats({ files, symbols, chunks })
    setShowRepoInput(false)

    // Auto-create a new chat session for the freshly indexed repo
    const newSession: Session = {
      id: crypto.randomUUID(),
      repoId,
      name: 'New Chat',
      createdAt: new Date().toISOString(),
      preview: '',
    }
    setSessions(prev => [newSession, ...prev])
    setActiveSessionId(newSession.id)
  }, [])

  // ── New Chat ───────────────────────────────────────────────────────
  const handleNewChat = useCallback(() => {
    if (!activeRepoId) {
      setShowRepoInput(true)
      return
    }
    const newSession: Session = {
      id: crypto.randomUUID(),
      repoId: activeRepoId,
      name: 'New Chat',
      createdAt: new Date().toISOString(),
      preview: '',
    }
    setSessions(prev => [newSession, ...prev])
    setActiveSessionId(newSession.id)
  }, [activeRepoId])

  // ── Select session from sidebar ────────────────────────────────────
  const handleSelectSession = useCallback((session: Session) => {
    setActiveSessionId(session.id)
    setActiveRepoId(session.repoId)
    setShowRepoInput(false)
  }, [])

  // ── Delete session ─────────────────────────────────────────────────
  const handleDeleteSession = useCallback((sessionId: string) => {
    setSessions(prev => {
      const filtered = prev.filter(s => s.id !== sessionId)
      // If the active session was deleted, switch to next available
      if (sessionId === activeSessionId) {
        const next = filtered[0] ?? null
        setActiveSessionId(next?.id ?? null)
        setActiveRepoId(next?.repoId ?? null)
      }
      return filtered
    })
  }, [activeSessionId])

  // ── Update session metadata when messages are sent ─────────────────
  const handleFirstMessage = useCallback((sessionId: string, text: string) => {
    setSessions(prev => prev.map(s =>
      s.id === sessionId
        ? { ...s, name: text.slice(0, 40) + (text.length > 40 ? '…' : '') }
        : s
    ))
  }, [])

  const handleMessageSent = useCallback((sessionId: string, preview: string) => {
    setSessions(prev => prev.map(s =>
      s.id === sessionId ? { ...s, preview: preview.slice(0, 60) } : s
    ))
  }, [])

  // ── Graph inspection ───────────────────────────────────────────────
  const handleInspectGraph = useCallback((
    graphCount: number,
    citations: string[],
    modelUsed: string,
  ) => {
    setDrawerGraphCount(graphCount)
    setDrawerCitations(citations)
    setDrawerModelUsed(modelUsed)
    setDrawerOpen(true)
  }, [])

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: 'var(--color-bg)' }}>

      {/* ── Left Sidebar ──────────────────────────────────────────── */}
      <Sidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewChat={handleNewChat}
        onIndexNewRepo={() => setShowRepoInput(true)}
        onDeleteSession={handleDeleteSession}
      />

      {/* ── Main Content ──────────────────────────────────────────── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>

        {/* Top Header */}
        <header style={{
          padding: '12px 20px',
          borderBottom: '1px solid var(--color-border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: 'var(--color-surface)',
          boxShadow: 'var(--shadow-sm)',
          flexShrink: 0,
          zIndex: 10,
        }}>
          {/* Active session info */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: 0 }}>
            {activeSession ? (
              <>
                <span style={{ fontSize: '16px' }}>💬</span>
                <div style={{ minWidth: 0 }}>
                  <div style={{
                    fontWeight: 600,
                    fontSize: '14px',
                    color: 'var(--color-text)',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    maxWidth: '300px',
                  }}>
                    {activeSession.name}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--color-muted)' }}>
                    📦 {activeSession.repoId}
                  </div>
                </div>
              </>
            ) : (
              <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--color-muted)' }}>
                Select or create a chat
              </div>
            )}
          </div>

          {/* Right actions */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexShrink: 0 }}>
            {activeRepoId && (
              <>
                <button
                  onClick={() => setEvalOpen(true)}
                  className="btn-ghost"
                  style={{ fontSize: '12px', padding: '5px 12px', display: 'flex', alignItems: 'center', gap: '5px' }}
                >
                  📊 Evaluation
                </button>
                <div className="active-repo-badge">
                  📌 <strong>{activeRepoId}</strong>
                </div>
              </>
            )}
          </div>
        </header>

        {/* Repo Input panel (collapsible) */}
        {showRepoInput && (
          <div style={{ flexShrink: 0 }}>
            <RepoInput
              onIngestSuccess={handleIngestSuccess}
              onStatusChange={(status, message) => {
                setIngestStatus(status)
                setStatusMessage(message)
              }}
            />
            <StatusBar
              status={ingestStatus}
              message={statusMessage}
              activeRepoId={activeRepoId}
              stats={repoStats}
            />
          </div>
        )}

        {/* Chat Panel — takes remaining space */}
        <ChatPanel
          repoId={activeRepoId}
          sessionId={activeSessionId}
          onInspectGraph={handleInspectGraph}
          onFirstMessage={handleFirstMessage}
          onMessageSent={handleMessageSent}
        />
      </div>

      {/* Graph Drawer */}
      <GraphDrawer
        isOpen={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        graphCount={drawerGraphCount}
        citations={drawerCitations}
        modelUsed={drawerModelUsed}
      />

      {/* Evaluation Dashboard */}
      <EvalDashboard
        isOpen={evalOpen}
        onClose={() => setEvalOpen(false)}
        activeRepoId={activeRepoId}
      />
    </div>
  )
}

export default App
