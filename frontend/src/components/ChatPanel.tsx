/**
 * components/ChatPanel.tsx
 * ------------------------
 * Chat interface for a single session.
 * Sends session_id with every query so LangGraph maintains Redis-backed history.
 * Messages are persisted to localStorage keyed by session so they survive refreshes.
 */

import { useState, useRef, useEffect, useCallback } from 'react'
import { Bot, Brain, Trash2, Lightbulb, Loader2 } from 'lucide-react'
import Message from './Message'
import { queryCodebase } from '../api/client'

const MESSAGES_KEY = 'coderag:messages'

function loadAllMessages(): Map<string, ChatMessage[]> {
  try {
    const raw = localStorage.getItem(MESSAGES_KEY)
    if (!raw) return new Map()
    const obj: Record<string, ChatMessage[]> = JSON.parse(raw)
    return new Map(Object.entries(obj))
  } catch {
    return new Map()
  }
}

function saveAllMessages(map: Map<string, ChatMessage[]>) {
  try {
    const obj = Object.fromEntries(map)
    localStorage.setItem(MESSAGES_KEY, JSON.stringify(obj))
  } catch {
    // ignore quota errors
  }
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: string[]
  modelUsed?: string
  graphNodesCount?: number
}

interface Props {
  repoId: string | null
  sessionId: string | null
  onInspectGraph: (graphCount: number, citations: string[], modelUsed: string) => void
  onFirstMessage: (sessionId: string, text: string) => void
  onMessageSent: (sessionId: string, preview: string) => void
}

export default function ChatPanel({
  repoId,
  sessionId,
  onInspectGraph,
  onFirstMessage,
  onMessageSent,
}: Props) {
  // Store messages per session — initialised from localStorage
  const [sessionMessages, setSessionMessages] = useState<Map<string, ChatMessage[]>>(loadAllMessages)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [useCodeModel, setUseCodeModel] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  // Derive current messages from the map
  const messages: ChatMessage[] = sessionId ? (sessionMessages.get(sessionId) ?? []) : []

  // Persist to localStorage whenever messages change
  useEffect(() => {
    saveAllMessages(sessionMessages)
  }, [sessionMessages])

  // Helper to update messages for a specific session
  const setMessages = useCallback((sid: string, updater: (prev: ChatMessage[]) => ChatMessage[]) => {
    setSessionMessages(prev => {
      const next = new Map(prev)
      next.set(sid, updater(next.get(sid) ?? []))
      return next
    })
  }, [])

  // Clear input when switching sessions
  useEffect(() => {
    setInput('')
  }, [sessionId])

  // Auto-scroll to latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || !repoId || !sessionId || loading) return

    const currentSessionId = sessionId
    const questionText = input.trim()
    const isFirstMessage = messages.length === 0

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: questionText,
    }

    setMessages(currentSessionId, prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const result = await queryCodebase(questionText, repoId, useCodeModel, currentSessionId)

      const aiMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: result.answer,
        citations: result.citations,
        modelUsed: result.model_used,
        graphNodesCount: result.graph_nodes_count,
      }
      setMessages(currentSessionId, prev => [...prev, aiMsg])

      // Notify parent to update session name (first message) and preview
      if (isFirstMessage) {
        onFirstMessage(currentSessionId, questionText)
      }
      onMessageSent(currentSessionId, questionText)

    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to generate response.'
      setMessages(currentSessionId, prev => [...prev, {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: `**Error:** ${message}`,
      }])
    } finally {
      setLoading(false)
    }
  }

  const isReady = repoId && sessionId

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      flex: 1,
      overflow: 'hidden',
      background: 'var(--color-bg)',
    }}>
      {/* Control Bar */}
      <div style={{
        padding: '10px 20px',
        background: 'var(--color-surface)',
        borderBottom: '1px solid var(--color-border)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
      }}>
        {/* Model selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
          <span style={{ color: 'var(--color-muted)', fontSize: '12px' }}>LLM Engine:</span>
          <button
            type="button"
            className={!useCodeModel ? 'btn-toggle active' : 'btn-toggle'}
            onClick={() => setUseCodeModel(false)}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}
          >
            <Bot size={13} /> Llama 3.3 70B
          </button>
          <button
            type="button"
            className={useCodeModel ? 'btn-toggle active' : 'btn-toggle'}
            onClick={() => setUseCodeModel(true)}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}
          >
            <Brain size={13} /> DeepSeek-Coder 70B
          </button>
        </div>

        {/* Clear chat */}
        {messages.length > 0 && sessionId && (
          <button
            onClick={() => setMessages(sessionId, () => [])}
            className="btn-ghost"
            style={{ fontSize: '12px', padding: '4px 10px', display: 'inline-flex', alignItems: 'center', gap: '5px' }}
          >
            <Trash2 size={13} /> Clear
          </button>
        )}
      </div>

      {/* Messages Scroll Area */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '24px 20px',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
      }}>
        {messages.length === 0 && (
          <div style={{
            color: 'var(--color-muted)',
            textAlign: 'center',
            marginTop: '80px',
            fontSize: '14px',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '12px',
          }}>
            <Lightbulb size={36} color="var(--color-muted-2)" strokeWidth={1.5} />
            {isReady ? (
              <>
                <div style={{ fontWeight: 600, color: 'var(--color-text)', fontSize: '15px' }}>
                  Repository <code>{repoId}</code> is ready!
                </div>
                <div style={{ color: 'var(--color-muted)', fontSize: '13px', maxWidth: '380px' }}>
                  Ask architecture questions like <em>"How does authentication work?"</em>
                  {' '}or <em>"What files import UserService?"</em>
                </div>
              </>
            ) : (
              <div style={{ color: 'var(--color-muted)', fontSize: '13px' }}>
                Select a chat from the sidebar or index a repository to begin.
              </div>
            )}
          </div>
        )}

        {messages.map(msg => (
          <Message
            key={msg.id}
            message={msg}
            onInspectGraph={onInspectGraph}
          />
        ))}

        {loading && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            color: 'var(--color-primary)',
            fontSize: '13px',
            padding: '12px 16px',
            background: 'var(--color-surface)',
            borderRadius: 'var(--radius-md)',
            border: '1.5px solid var(--color-border)',
            width: 'fit-content',
            boxShadow: 'var(--shadow-sm)',
          }}>
            <Loader2 size={16} className="spinner" />
            <span>Hybrid Vector + Neo4j Cypher Graph Expansion…</span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input Bar */}
      <form
        onSubmit={handleSubmit}
        style={{
          padding: '14px 20px 18px',
          borderTop: '1px solid var(--color-border)',
          background: 'var(--color-surface)',
          display: 'flex',
          gap: '10px',
          boxShadow: '0 -2px 8px rgba(0,0,0,0.04)',
        }}
      >
        <input
          type="text"
          placeholder={
            !repoId ? 'Index a repository first…' :
            !sessionId ? 'Select or create a chat first…' :
            `Ask anything about ${repoId}…`
          }
          value={input}
          onChange={e => setInput(e.target.value)}
          disabled={!isReady || loading}
          style={{ flex: 1 }}
        />
        <button
          type="submit"
          className="btn-primary"
          disabled={!isReady || loading || !input.trim()}
        >
          {loading ? 'Searching…' : 'Send →'}
        </button>
      </form>
    </div>
  )
}
