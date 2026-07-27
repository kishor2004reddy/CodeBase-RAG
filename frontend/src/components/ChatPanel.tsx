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
  onInspectGraph: (graphCount: number, citations: string[], modelUsed: string) => void
}

export default function ChatPanel({ repoId, onInspectGraph }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [useCodeModel, setUseCodeModel] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || !repoId || loading) return

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: input.trim(),
    }

    setMessages(prev => [...prev, userMsg])
    const questionText = input.trim()
    setInput('')
    setLoading(true)

    try {
      const result = await queryCodebase(questionText, repoId, useCodeModel)
      const aiMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: result.answer,
        citations: result.citations,
        modelUsed: result.model_used,
        graphNodesCount: result.graph_nodes_count,
      }
      setMessages(prev => [...prev, aiMsg])
    } catch (err: any) {
      setMessages(prev => [...prev, {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: `⚠️ Error: ${err.message || 'Failed to generate response.'}`,
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
      position: 'relative',
    }}>
      {/* Control Bar: Model Toggle & Clear */}
      <div style={{
        padding: '10px 24px',
        background: 'var(--color-surface)',
        borderBottom: '1px solid var(--color-border)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
      }}>
        {/* Model selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
          <span style={{ color: 'var(--color-muted)' }}>LLM Engine:</span>
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
            style={{ fontSize: '12px', padding: '3px 10px' }}
          >
            🗑️ Clear Chat
          </button>
        )}
      </div>

      {/* Messages Scroll Area */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '20px 24px',
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
            <span style={{ fontSize: '32px' }}>💡</span>
            <div>
              {repoId ? (
                <>
                  <strong>Repository <code style={{ color: 'var(--color-primary)' }}>{repoId}</code> is ready!</strong>
                  <div style={{ marginTop: '6px', color: 'var(--color-muted)', fontSize: '13px' }}>
                    Ask architecture questions like: <em>"How does authentication work?"</em> or <em>"What files import UserService?"</em>
                  </div>
                </>
              ) : (
                'Index a GitHub repository or upload a ZIP file above to begin querying.'
              )}
            </div>
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
            fontSize: '14px',
            padding: '12px 16px',
            background: 'var(--color-surface)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--color-border)',
            width: 'fit-content',
          }}>
            <span className="spinner">⏳</span>
            <span>Performing Hybrid Vector + Neo4j Cypher Graph Expansion...</span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input Bar */}
      <form
        onSubmit={handleSubmit}
        style={{
          padding: '16px 24px 20px',
          borderTop: '1px solid var(--color-border)',
          background: 'var(--color-surface)',
          display: 'flex',
          gap: '12px',
        }}
      >
        <input
          type="text"
          placeholder={repoId ? `Ask anything about ${repoId}...` : 'Index a repository first...'}
          value={input}
          onChange={e => setInput(e.target.value)}
          disabled={!repoId || loading}
          style={{ flex: 1 }}
        />
        <button
          type="submit"
          className="btn-primary"
          disabled={!repoId || loading || !input.trim()}
        >
          {loading ? 'Searching...' : 'Send Question'}
        </button>
      </form>
    </div>
  )
}
