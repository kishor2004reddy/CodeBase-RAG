/**
 * components/Sidebar.tsx
 * ----------------------
 * Resizable left sidebar showing chat sessions per indexed repo.
 *
 * Features:
 *  - Horizontally resizable via drag handle (min 180px, max 420px)
 *  - "New Chat" button at the top — always opens the repo ingestion form,
 *    since every chat must be scoped to exactly one indexed repository.
 *  - Sessions grouped by repo, stored in localStorage
 *  - Active session highlighting
 *  - Delete individual sessions, or an entire repo (+ all its chats)
 */

import { useRef, useState, useEffect, useCallback } from 'react'
import { Network, SquarePen, MessageSquare, Package, Trash2, Loader2 } from 'lucide-react'
import { deleteSession, deleteRepo } from '../api/client'

export interface Session {
  id: string          // UUID — maps to LangGraph thread_id in Redis
  repoId: string
  name: string        // auto-derived from first user message (first 40 chars)
  createdAt: string
  preview: string     // last message preview
}

interface Props {
  sessions: Session[]
  activeSessionId: string | null
  onSelectSession: (session: Session) => void
  onNewChat: () => void
  onDeleteSession: (sessionId: string) => void
  onDeleteRepo: (repoId: string) => void
}

const MIN_WIDTH = 180
const MAX_WIDTH = 420
const DEFAULT_WIDTH = 260

export default function Sidebar({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  onDeleteSession,
  onDeleteRepo,
}: Props) {
  const [width, setWidth] = useState(DEFAULT_WIDTH)
  const [isDragging, setIsDragging] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [deletingRepoId, setDeletingRepoId] = useState<string | null>(null)
  const dragStartX = useRef(0)
  const dragStartWidth = useRef(DEFAULT_WIDTH)

  // ── Drag-to-resize logic ────────────────────────────────────────────
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    setIsDragging(true)
    dragStartX.current = e.clientX
    dragStartWidth.current = width
  }, [width])

  useEffect(() => {
    if (!isDragging) return

    const handleMouseMove = (e: MouseEvent) => {
      const delta = e.clientX - dragStartX.current
      const newWidth = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, dragStartWidth.current + delta))
      setWidth(newWidth)
    }

    const handleMouseUp = () => setIsDragging(false)

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDragging])

  // ── Delete session ──────────────────────────────────────────────────
  const handleDelete = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation()
    setDeletingId(sessionId)
    try {
      await deleteSession(sessionId)
    } catch {
      // Best effort — remove locally even if backend fails
    } finally {
      onDeleteSession(sessionId)
      setDeletingId(null)
    }
  }

  // ── Delete an entire repo (its indexed data + every chat under it) ───
  const handleDeleteRepo = async (e: React.MouseEvent, repoId: string, repoSessions: Session[]) => {
    e.stopPropagation()
    const confirmed = window.confirm(
      `Delete "${repoId}"?\n\nThis permanently removes its indexed data (vectors + graph) ` +
      `and all ${repoSessions.length} chat${repoSessions.length === 1 ? '' : 's'} under it. This cannot be undone.`
    )
    if (!confirmed) return

    setDeletingRepoId(repoId)
    try {
      await deleteRepo(repoId)
    } catch {
      // Best effort — still clean up locally even if backend call fails
    }
    // Also wipe each chat's Redis-backed conversation memory
    await Promise.all(repoSessions.map(s => deleteSession(s.id).catch(() => {})))
    onDeleteRepo(repoId)
    setDeletingRepoId(null)
  }

  // Group sessions by repo
  const grouped = sessions.reduce<Record<string, Session[]>>((acc, s) => {
    if (!acc[s.repoId]) acc[s.repoId] = []
    acc[s.repoId].push(s)
    return acc
  }, {})

  return (
    <div style={{ display: 'flex', height: '100%', flexShrink: 0 }}>
      {/* ── Sidebar panel ── */}
      <div
        style={{
          width: `${width}px`,
          minWidth: `${MIN_WIDTH}px`,
          maxWidth: `${MAX_WIDTH}px`,
          height: '100%',
          background: 'var(--color-sidebar)',
          borderRight: '1px solid var(--color-border)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          flexShrink: 0,
          userSelect: isDragging ? 'none' : 'auto',
        }}
      >
        {/* Logo area */}
        <div style={{
          padding: '16px 16px 12px',
          borderBottom: '1px solid var(--color-border)',
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
        }}>
          <div style={{
            width: '30px',
            height: '30px',
            borderRadius: 'var(--radius-sm)',
            background: 'var(--color-primary)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}>
            <Network size={16} color="#fff" />
          </div>
          {width > 200 && (
            <div>
              <div style={{ fontWeight: 700, fontSize: '13px', color: 'var(--color-text)', lineHeight: 1.2 }}>
                CodeGraphRAG
              </div>
              <div style={{ fontSize: '10px', color: 'var(--color-muted)', marginTop: '1px' }}>
                Codebase Intelligence
              </div>
            </div>
          )}
        </div>

        {/* Action buttons */}
        <div style={{ padding: '12px 12px 4px' }}>
          {/* New Chat — always starts by indexing a repo */}
          <button
            className="sidebar-new-chat-btn"
            onClick={onNewChat}
            title="Start a new chat by indexing a repository"
          >
            <SquarePen size={15} />
            {width > 200 && <span>New Chat</span>}
          </button>
        </div>

        {/* Session list */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '4px 10px 16px' }}>
          {sessions.length === 0 && (
            <div style={{
              textAlign: 'center',
              color: 'var(--color-muted-2)',
              fontSize: '12px',
              marginTop: '32px',
              padding: '0 8px',
              lineHeight: 1.8,
            }}>
              {width > 200 ? (
                <>
                  <MessageSquare size={22} strokeWidth={1.5} style={{ marginBottom: '8px' }} />
                  <div>No chats yet.</div>
                  <div>Index a repo to start.</div>
                </>
              ) : (
                <MessageSquare size={18} strokeWidth={1.5} />
              )}
            </div>
          )}

          {Object.entries(grouped).map(([repoId, repoSessions]) => (
            <div key={repoId}>
              {width > 200 && (
                <div className="sidebar-repo-header sidebar-section-label" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '4px' }}>
                  <span style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}>
                    <Package size={11} /> {repoId.length > 22 ? repoId.slice(0, 22) + '…' : repoId}
                  </span>
                  <button
                    onClick={(e) => handleDeleteRepo(e, repoId, repoSessions)}
                    disabled={deletingRepoId === repoId}
                    title="Delete this repo and all its chats"
                    className="repo-delete-btn"
                    style={{
                      background: 'transparent',
                      border: 'none',
                      cursor: 'pointer',
                      color: 'var(--color-muted-2)',
                      padding: '2px 4px',
                      borderRadius: 'var(--radius-sm)',
                      opacity: 0,
                      transition: 'opacity 0.15s, color 0.15s',
                      flexShrink: 0,
                      display: 'flex',
                      alignItems: 'center',
                    }}
                    onMouseEnter={e => (e.currentTarget as HTMLElement).style.color = 'var(--color-error)'}
                    onMouseLeave={e => (e.currentTarget as HTMLElement).style.color = 'var(--color-muted-2)'}
                  >
                    {deletingRepoId === repoId ? <Loader2 size={11} className="spinner" /> : <Trash2 size={11} />}
                  </button>
                </div>
              )}
              {repoSessions.map(session => (
                <div key={session.id} style={{ position: 'relative' }}>
                  <button
                    className={`sidebar-session-item${session.id === activeSessionId ? ' active' : ''}`}
                    onClick={() => onSelectSession(session)}
                    title={session.name}
                  >
                    {width > 200 ? (
                      <>
                        <span style={{
                          fontSize: '12px',
                          fontWeight: 600,
                          color: session.id === activeSessionId ? 'var(--color-primary)' : 'var(--color-text)',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          maxWidth: '100%',
                          display: 'block',
                        }}>
                          {session.name}
                        </span>
                        <span style={{
                          fontSize: '11px',
                          color: 'var(--color-muted)',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          maxWidth: '100%',
                          display: 'block',
                        }}>
                          {session.preview || 'No messages yet'}
                        </span>
                      </>
                    ) : (
                      <MessageSquare size={16} strokeWidth={1.5} />
                    )}
                  </button>
                  {/* Delete button */}
                  {width > 200 && (
                    <button
                      onClick={(e) => handleDelete(e, session.id)}
                      disabled={deletingId === session.id}
                      title="Delete this chat"
                      style={{
                        position: 'absolute',
                        right: '6px',
                        top: '50%',
                        transform: 'translateY(-50%)',
                        background: 'transparent',
                        border: 'none',
                        cursor: 'pointer',
                        color: 'var(--color-muted-2)',
                        fontSize: '12px',
                        padding: '3px 5px',
                        borderRadius: 'var(--radius-sm)',
                        opacity: 0,
                        transition: 'opacity 0.15s, color 0.15s',
                      }}
                      className="session-delete-btn"
                      onMouseEnter={e => (e.currentTarget as HTMLElement).style.color = 'var(--color-error)'}
                      onMouseLeave={e => (e.currentTarget as HTMLElement).style.color = 'var(--color-muted-2)'}
                    >
                      {deletingId === session.id ? <Loader2 size={12} className="spinner" /> : <Trash2 size={12} />}
                    </button>
                  )}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* ── Drag handle ── */}
      <div
        className={`resize-handle${isDragging ? ' dragging' : ''}`}
        onMouseDown={handleMouseDown}
        style={{ cursor: isDragging ? 'col-resize' : undefined }}
      />

      {/* Prevent text selection overlay while dragging */}
      {isDragging && (
        <div style={{
          position: 'fixed',
          inset: 0,
          cursor: 'col-resize',
          zIndex: 9999,
        }} />
      )}
    </div>
  )
}
