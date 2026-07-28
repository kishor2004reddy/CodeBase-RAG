/**
 * components/Sidebar.tsx
 * ----------------------
 * Resizable left sidebar showing chat sessions per indexed repo.
 *
 * Features:
 *  - Horizontally resizable via drag handle (min 180px, max 420px)
 *  - "New Chat" button at the top
 *  - "Index New Repo" option
 *  - Sessions grouped by repo, stored in localStorage
 *  - Active session highlighting
 *  - Delete individual sessions
 */

import { useRef, useState, useEffect, useCallback } from 'react'
import { deleteSession } from '../api/client'

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
  onIndexNewRepo: () => void
  onDeleteSession: (sessionId: string) => void
}

const MIN_WIDTH = 180
const MAX_WIDTH = 420
const DEFAULT_WIDTH = 260

export default function Sidebar({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  onIndexNewRepo,
  onDeleteSession,
}: Props) {
  const [width, setWidth] = useState(DEFAULT_WIDTH)
  const [isDragging, setIsDragging] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)
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
            fontSize: '16px',
            flexShrink: 0,
          }}>
            🕸️
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
          {/* New Chat */}
          <button
            className="sidebar-new-chat-btn"
            onClick={onNewChat}
            title="Start a new conversation"
          >
            <span style={{ fontSize: '15px' }}>✏️</span>
            {width > 200 && <span>New Chat</span>}
          </button>

          {/* Index new repo */}
          <button
            onClick={onIndexNewRepo}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              width: '100%',
              padding: '8px 12px',
              background: 'transparent',
              border: '1.5px dashed var(--color-border)',
              borderRadius: 'var(--radius-md)',
              fontSize: '12px',
              fontWeight: 500,
              color: 'var(--color-muted)',
              cursor: 'pointer',
              fontFamily: 'var(--font-sans)',
              transition: 'all 0.15s',
            }}
            onMouseEnter={e => {
              (e.currentTarget as HTMLElement).style.borderColor = 'var(--color-primary)'
              ;(e.currentTarget as HTMLElement).style.color = 'var(--color-primary)'
              ;(e.currentTarget as HTMLElement).style.background = 'var(--color-primary-soft)'
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLElement).style.borderColor = 'var(--color-border)'
              ;(e.currentTarget as HTMLElement).style.color = 'var(--color-muted)'
              ;(e.currentTarget as HTMLElement).style.background = 'transparent'
            }}
            title="Index a new repository"
          >
            <span>➕</span>
            {width > 200 && <span>Index New Repo</span>}
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
                  <div style={{ fontSize: '22px', marginBottom: '8px' }}>💬</div>
                  <div>No chats yet.</div>
                  <div>Index a repo to start.</div>
                </>
              ) : (
                <div style={{ fontSize: '18px' }}>💬</div>
              )}
            </div>
          )}

          {Object.entries(grouped).map(([repoId, repoSessions]) => (
            <div key={repoId}>
              {width > 200 && (
                <div className="sidebar-section-label">
                  📦 {repoId.length > 22 ? repoId.slice(0, 22) + '…' : repoId}
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
                      <span style={{ fontSize: '16px' }}>💬</span>
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
                      {deletingId === session.id ? '…' : '🗑'}
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
