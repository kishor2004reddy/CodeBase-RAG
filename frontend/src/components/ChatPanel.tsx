/**
 * components/ChatPanel.tsx
 * ------------------------
 * Chat interface for a single session.
 * Sends session_id with every query so LangGraph maintains Redis-backed history.
 */

import { useState, useRef, useEffect } from 'react'
import Message from './Message'
import { queryCodebase } from '../api/client'

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
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [useCodeModel, setUseCodeModel] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  // Reset messages when session changes
  useEffect(() => {
    setMessages([])
    setInput('')
  }, [sessionId])

  // Auto-scroll to latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || !repoId || !sessionId || loading) return

    const questionText = input.trim()
    const isFirstMessage = messages.length === 0

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: questionText,
    }

    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const result = await queryCodebase(questionText, repoId, useCodeModel, sessionId)

      const aiMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: result.answer,
        citations: result.citations,
        modelUsed: result.model_used,
        graphNodesCount: result.graph_nodes_count,
      }
      setMessages(prev => [...prev, aiMsg])

      // Notify parent to update session name (first message) and preview
      if (isFirstMessage) {
        onFirstMessage(sessionId, questionText)
      }
      onMessageSent(sessionId, questionText)

    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to generate response.'
      setMessages(prev => [...prev, {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: `⚠️ Error: ${message}`,
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
          >
            🦙 Llama 3.3 70B
          </button>
          <button
            type="button"
            className={useCodeModel ? 'btn-toggle active' : 'btn-toggle'}
            onClick={() => setUseCodeModel(true)}
          >
            🧠 DeepSeek-Coder 70B
          </button>
        </div>

        {/* Clear chat */}
        {messages.length > 0 && (
          <button
            onClick={() => setMessages([])}
            className="btn-ghost"
            style={{ fontSize: '12px', padding: '4px 10px' }}
          >
            🗑️ Clear
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
            <span style={{ fontSize: '36px' }}>💡</span>
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
            <span className="spinner">⏳</span>
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
