import type { ChatMessage } from './ChatPanel'

interface Props {
  message: ChatMessage
  onInspectGraph?: (graphCount: number, citations: string[], modelUsed: string) => void
}

export default function Message({ message, onInspectGraph }: Props) {
  const isUser = message.role === 'user'

  return (
    <div style={{
      display: 'flex',
      justifyContent: isUser ? 'flex-end' : 'flex-start',
    }}>
      <div style={{
        maxWidth: '85%',
        width: isUser ? 'auto' : '100%',
        background: isUser ? 'var(--color-user-msg)' : 'var(--color-ai-msg)',
        border: '1px solid var(--color-border)',
        borderRadius: isUser
          ? 'var(--radius-md) var(--radius-md) 2px var(--radius-md)'
          : 'var(--radius-md) var(--radius-md) var(--radius-md) 2px',
        padding: '14px 18px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
      }}>
        {/* Role header & badges */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '8px',
        }}>
          <div style={{
            fontSize: '12px',
            fontWeight: 600,
            color: isUser ? 'var(--color-primary)' : 'var(--color-success)',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}>
            <span>{isUser ? '👤 You' : '⚡ CodeGraphRAG'}</span>
          </div>

          {!isUser && message.modelUsed && (
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <span className="badge-model">
                {message.modelUsed.includes('deepseek') ? '🧠 DeepSeek-Coder' : '🦙 Llama 3.3'}
              </span>
              {message.graphNodesCount !== undefined && onInspectGraph && (
                <button
                  onClick={() => onInspectGraph(
                    message.graphNodesCount || 0,
                    message.citations || [],
                    message.modelUsed || ''
                  )}
                  className="btn-ghost"
                  style={{ fontSize: '11px', padding: '2px 8px' }}
                >
                  🕸️ {message.graphNodesCount} Graph Nodes
                </button>
              )}
            </div>
          )}
        </div>

        {/* Content */}
        <div style={{ fontSize: '14px', whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
          {message.content}
        </div>

        {/* Citations list */}
        {message.citations && message.citations.length > 0 && (
          <div style={{ marginTop: '14px', borderTop: '1px solid var(--color-border)', paddingTop: '10px' }}>
            <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-muted)', marginBottom: '6px' }}>
              📌 GROUNDED CODE CITATIONS ({message.citations.length})
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
              {message.citations.map((cite, i) => (
                <span
                  key={i}
                  className="citation-chip"
                  title="Grounded file reference"
                >
                  📄 {cite}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
