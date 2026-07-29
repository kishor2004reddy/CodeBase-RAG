/**
 * App.tsx
 * -------
 * Root layout: resizable sidebar (left) + main content area (right).
 *
 * Session management:
 *  - Sessions stored in localStorage (id, repoId, name, preview, createdAt)
 *  - Active session_id sent to backend for LangGraph Redis-backed memory
 *  - Every chat is scoped to exactly one indexed repo — "New Chat" always
 *    opens the repo ingestion form first; the session itself is only
 *    created once ingestion succeeds (see handleIngestSuccess).
 */

import { useState, useCallback, useEffect } from 'react'
import { MessageSquare, Package, BarChart3, Pin, FolderPlus } from 'lucide-react'
import Sidebar, { type Session } from './components/Sidebar'
import RepoInput from './components/RepoInput'
import ChatPanel from './components/ChatPanel'
import GraphDrawer from './components/GraphDrawer'
import EvalDashboard from './components/EvalDashboard'

const SESSIONS_KEY = 'coderag:sessions'
const ACTIVE_KEY = 'coderag:active'

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

interface ActiveState {
  sessionId: string | null
  repoId: string | null
}

function loadActive(): ActiveState {
  try {
    return JSON.parse(localStorage.getItem(ACTIVE_KEY) || 'null') ?? { sessionId: null, repoId: null }
  } catch {
    return { sessionId: null, repoId: null }
  }
}

function saveActive(active: ActiveState) {
  localStorage.setItem(ACTIVE_KEY, JSON.stringify(active))
}

// Restore the last-active chat on reload. Falls back to the most recently
// created session if the saved one was deleted or is otherwise invalid.
function resolveInitialActive(sessions: Session[]): ActiveState {
  const stored = loadActive()
  const matched = sessions.find(s => s.id === stored.sessionId)
  if (matched) return { sessionId: matched.id, repoId: matched.repoId }
  if (sessions.length > 0) return { sessionId: sessions[0].id, repoId: sessions[0].repoId }
  return { sessionId: null, repoId: null }
}

function App() {
  // Session state — restore the previously active chat on reload, so a
  // restart of the app/backend doesn't make the chat appear to "vanish".
  const [sessions, setSessions] = useState<Session[]>(loadSessions)
  const [activeSessionId, setActiveSessionId] = useState<string | null>(
    () => resolveInitialActive(loadSessions()).sessionId
  )
  const [activeRepoId, setActiveRepoId] = useState<string | null>(
    () => resolveInitialActive(loadSessions()).repoId
  )
  const [showRepoInput, setShowRepoInput] = useState<boolean>(
    () => resolveInitialActive(loadSessions()).sessionId === null
  )

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

  // Persist the active session/repo so a reload resumes the same chat
  useEffect(() => {
    saveActive({ sessionId: activeSessionId, repoId: activeRepoId })
  }, [activeSessionId, activeRepoId])

  const activeSession = sessions.find(s => s.id === activeSessionId) ?? null

  // ── Repo ingestion success ─────────────────────────────────────────
  // ── Repo ingestion success ────────────────────────────
  const handleIngestSuccess = useCallback((repoId: string) => {
    setActiveRepoId(repoId)
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

  // ── New Chat — always requires indexing a repo before chatting ──────
  // The session itself is created in handleIngestSuccess once the newly
  // (re-)indexed repo is ready, so every chat maps to exactly one repo.
  const handleNewChat = useCallback(() => {
    setShowRepoInput(true)
  }, [])

  // ── Cancel out of the ingest form back to the previously active chat ─
  const handleCancelRepoInput = useCallback(() => {
    setShowRepoInput(false)
  }, [])

  // ── Select session from sidebar ────────────────────────────────────
  const handleSelectSession = useCallback((session: Session) => {
    setActiveSessionId(session.id)
    setActiveRepoId(session.repoId)
    setShowRepoInput(false)
  }, [])

  // ── Delete session ─────────────────────────────────────────────────
  const handleDeleteSession = useCallback((sessionId: string) => {
    // Also remove persisted messages for this session from localStorage
    try {
      const raw = localStorage.getItem('coderag:messages')
      if (raw) {
        const obj = JSON.parse(raw)
        delete obj[sessionId]
        localStorage.setItem('coderag:messages', JSON.stringify(obj))
      }
    } catch { /* ignore */ }

    setSessions(prev => {
      const filtered = prev.filter(s => s.id !== sessionId)
      // If the active session was deleted, switch to next available
      if (sessionId === activeSessionId) {
        const next = filtered[0] ?? null
        setActiveSessionId(next?.id ?? null)
        setActiveRepoId(next?.repoId ?? null)
        setShowRepoInput(next === null)
      }
      return filtered
    })
  }, [activeSessionId])

  // ── Delete an entire repo (indexed data + every chat under it) ──────
  // The Sidebar already deletes the repo's Qdrant/Neo4j data and each
  // affected session's Redis memory — this just cleans up local state.
  const handleDeleteRepo = useCallback((repoId: string) => {
    setSessions(prev => {
      const removedIds = prev.filter(s => s.repoId === repoId).map(s => s.id)

      try {
        const raw = localStorage.getItem('coderag:messages')
        if (raw) {
          const obj = JSON.parse(raw)
          removedIds.forEach(id => delete obj[id])
          localStorage.setItem('coderag:messages', JSON.stringify(obj))
        }
      } catch { /* ignore */ }

      const filtered = prev.filter(s => s.repoId !== repoId)

      // If the deleted repo was active, switch to the next available chat
      if (repoId === activeRepoId) {
        const next = filtered[0] ?? null
        setActiveSessionId(next?.id ?? null)
        setActiveRepoId(next?.repoId ?? null)
        setShowRepoInput(next === null)
      }
      return filtered
    })
  }, [activeRepoId])

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
        onDeleteSession={handleDeleteSession}
        onDeleteRepo={handleDeleteRepo}
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
          {/* Active session info — replaced by an indexing indicator while showRepoInput is true */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: 0 }}>
            {showRepoInput ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 600, fontSize: '14px', color: 'var(--color-muted)' }}>
                <FolderPlus size={16} color="var(--color-primary)" />
                Starting a new chat…
              </div>
            ) : activeSession ? (
              <>
                <MessageSquare size={16} color="var(--color-primary)" style={{ flexShrink: 0 }} />
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
                  <div style={{ fontSize: '11px', color: 'var(--color-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <Package size={11} /> {activeSession.repoId}
                  </div>
                </div>
              </>
            ) : (
              <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--color-muted)' }}>
                Select or create a chat
              </div>
            )}
          </div>

          {/* Right actions — hidden while indexing, since there's no "current" chat context */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexShrink: 0 }}>
            {!showRepoInput && activeRepoId && (
              <>
                <button
                  onClick={() => setEvalOpen(true)}
                  className="btn-ghost"
                  style={{ fontSize: '12px', padding: '5px 12px', display: 'flex', alignItems: 'center', gap: '5px' }}
                >
                  <BarChart3 size={13} /> Evaluation
                </button>
                <div className="active-repo-badge" style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                  <Pin size={12} /> <strong>{activeRepoId}</strong>
                </div>
              </>
            )}
          </div>
        </header>

        {/* Repo Input view — fully replaces the chat while indexing a repo */}
        {showRepoInput ? (
          <div style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            overflowY: 'auto',
            padding: '32px 20px',
          }}>
            <div style={{
              width: '100%',
              maxWidth: '620px',
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-lg)',
              boxShadow: 'var(--shadow-md)',
              overflow: 'hidden',
            }}>
              <RepoInput
                onIngestSuccess={handleIngestSuccess}
                onCancel={activeSessionId ? handleCancelRepoInput : undefined}
              />
            </div>
          </div>
        ) : (
          <ChatPanel
            repoId={activeRepoId}
            sessionId={activeSessionId}
            onInspectGraph={handleInspectGraph}
            onFirstMessage={handleFirstMessage}
            onMessageSent={handleMessageSent}
          />
        )}
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
