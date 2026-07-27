import type { ChatMessage } from './ChatPanel'

interface Props {
  message: ChatMessage
}

export default function Message({ message }: Props) {
  const isUser = message.role === 'user'

  return (
    <div style={{
      display: 'flex',
      justifyContent: isUser ? 'flex-end' : 'flex-start',
    }}>
      <div style={{
        maxWidth: '80%',
        background: isUser ? 'var(--color-user-msg)' : 'var(--color-ai-msg)',
        border: '1px solid var(--color-border)',
        borderRadius: isUser
          ? 'var(--radius-md) var(--radius-md) 2px var(--radius-md)'
          : 'var(--radius-md) var(--radius-md) var(--radius-md) 2px',
        padding: '10px 14px',
      }}>
        {/* Role label */}
        <div style={{
          fontSize: '11px',
          fontWeight: 600,
          color: isUser ? 'var(--color-primary)' : 'var(--color-success)',
          marginBottom: '6px',
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
        }}>
          {isUser ? 'You' : 'CodeGraphRAG'}
        </div>

        {/* Content */}
        <div style={{ fontSize: '14px', whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
          {message.content}
        </div>

        {/* Citations */}
        {message.citations && message.citations.length > 0 && (
          <div style={{ marginTop: '10px', borderTop: '1px solid var(--color-border)', paddingTop: '8px' }}>
            <div style={{ fontSize: '11px', color: 'var(--color-muted)', marginBottom: '4px' }}>
              📎 Sources
            </div>
            {message.citations.map((cite, i) => (
              <div key={i} style={{
                fontSize: '12px',
                fontFamily: 'var(--font-mono)',
                color: 'var(--color-primary)',
                padding: '2px 0',
              }}>
                {cite}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
