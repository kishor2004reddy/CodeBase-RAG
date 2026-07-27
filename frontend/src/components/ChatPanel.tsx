import { useState, useRef, useEffect } from 'react'
import Message from './Message'
import { queryRepo } from '../api/client'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: string[]
}

interface Props {
  enabled: boolean
}

export default function ChatPanel({ enabled }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || loading) return

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: input.trim(),
    }

    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const result = await queryRepo(userMsg.content)
      const aiMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: result.answer,
        citations: result.citations,
      }
      setMessages(prev => [...prev, aiMsg])
    } catch {
      setMessages(prev => [...prev, {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: '⚠️ Something went wrong. Please try again.',
      }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      flex: 1,
      overflow: 'hidden',
    }}>
      {/* Messages */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '16px 24px',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
      }}>
        {messages.length === 0 && (
          <div style={{
            color: 'var(--color-muted)',
            textAlign: 'center',
            marginTop: '60px',
            fontSize: '14px',
          }}>
            {enabled
              ? 'Repository indexed ✅ — ask anything about the codebase.'
              : 'Index a repository above to get started.'}
          </div>
        )}
        {messages.map(msg => (
          <Message key={msg.id} message={msg} />
        ))}
        {loading && (
          <div style={{ color: 'var(--color-muted)', fontSize: '14px', fontStyle: 'italic' }}>
            Thinking...
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form
        onSubmit={handleSubmit}
        style={{
          padding: '12px 24px 20px',
          borderTop: '1px solid var(--color-border)',
          display: 'flex',
          gap: '10px',
        }}
      >
        <input
          type="text"
          placeholder={enabled ? 'Ask about the codebase...' : 'Index a repo first...'}
          value={input}
          onChange={e => setInput(e.target.value)}
          disabled={!enabled || loading}
          style={{ flex: 1 }}
        />
        <button
          type="submit"
          className="btn-primary"
          disabled={!enabled || loading || !input.trim()}
        >
          Ask
        </button>
      </form>
    </div>
  )
}
