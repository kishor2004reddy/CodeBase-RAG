import { User, Zap, Bot, Brain, Network, Pin, FileText } from 'lucide-react'
import type { ChatMessage } from './ChatPanel'

interface Props {
  message: ChatMessage
  onInspectGraph?: (graphCount: number, citations: string[], modelUsed: string) => void
}

// ── Inline Markdown renderer ──────────────────────────────────────────────────
// Handles: **bold**, *italic*, `inline code`, [text](url)
function renderInline(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = []
  // Combined regex for inline tokens
  const re = /(\*\*(.+?)\*\*)|(\*(.+?)\*)|(`([^`]+)`)|(\[([^\]]+)\]\(([^)]+)\))/g
  let last = 0
  let match: RegExpExecArray | null

  while ((match = re.exec(text)) !== null) {
    if (match.index > last) parts.push(text.slice(last, match.index))

    if (match[1]) {
      // **bold**
      parts.push(<strong key={match.index}>{match[2]}</strong>)
    } else if (match[3]) {
      // *italic*
      parts.push(<em key={match.index}>{match[4]}</em>)
    } else if (match[5]) {
      // `code`
      parts.push(
        <code key={match.index} style={{
          background: 'var(--color-code-bg, rgba(99,102,241,0.12))',
          color: 'var(--color-primary)',
          borderRadius: '4px',
          padding: '1px 5px',
          fontSize: '0.875em',
          fontFamily: 'monospace',
        }}>{match[6]}</code>
      )
    } else if (match[7]) {
      // [text](url)
      parts.push(
        <a key={match.index} href={match[9]} target="_blank" rel="noreferrer"
          style={{ color: 'var(--color-primary)', textDecoration: 'underline' }}>
          {match[8]}
        </a>
      )
    }
    last = match.index + match[0].length
  }

  if (last < text.length) parts.push(text.slice(last))
  return parts
}

// ── Block Markdown renderer ───────────────────────────────────────────────────
function MarkdownBlock({ content }: { content: string }) {
  const lines = content.split('\n')
  const nodes: React.ReactNode[] = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]

    // Fenced code block ```
    if (line.startsWith('```')) {
      const lang = line.slice(3).trim()
      const codeLines: string[] = []
      i++
      while (i < lines.length && !lines[i].startsWith('```')) {
        codeLines.push(lines[i])
        i++
      }
      nodes.push(
        <pre key={i} style={{
          background: 'rgba(0,0,0,0.35)',
          border: '1px solid var(--color-border)',
          borderRadius: '8px',
          padding: '14px 16px',
          overflowX: 'auto',
          fontSize: '13px',
          lineHeight: 1.6,
          margin: '10px 0',
          fontFamily: 'monospace',
        }}>
          {lang && (
            <div style={{ fontSize: '11px', color: 'var(--color-muted)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              {lang}
            </div>
          )}
          <code>{codeLines.join('\n')}</code>
        </pre>
      )
      i++
      continue
    }

    // Headings
    const headingMatch = line.match(/^(#{1,6})\s+(.+)/)
    if (headingMatch) {
      const level = headingMatch[1].length
      const text = headingMatch[2]
      const sizes: Record<number, string> = { 1: '1.35em', 2: '1.2em', 3: '1.08em', 4: '1em', 5: '0.95em', 6: '0.9em' }
      nodes.push(
        <div key={i} style={{
          fontSize: sizes[level] || '1em',
          fontWeight: 700,
          color: 'var(--color-text)',
          marginTop: level <= 2 ? '18px' : '12px',
          marginBottom: '6px',
          borderBottom: level === 1 ? '1px solid var(--color-border)' : undefined,
          paddingBottom: level === 1 ? '6px' : undefined,
        }}>
          {renderInline(text)}
        </div>
      )
      i++
      continue
    }

    // Horizontal rule
    if (/^[-*_]{3,}$/.test(line.trim())) {
      nodes.push(<hr key={i} style={{ border: 'none', borderTop: '1px solid var(--color-border)', margin: '14px 0' }} />)
      i++
      continue
    }

    // Blockquote
    if (line.startsWith('> ')) {
      nodes.push(
        <blockquote key={i} style={{
          borderLeft: '3px solid var(--color-primary)',
          paddingLeft: '12px',
          margin: '8px 0',
          color: 'var(--color-muted)',
          fontStyle: 'italic',
        }}>
          {renderInline(line.slice(2))}
        </blockquote>
      )
      i++
      continue
    }

    // Unordered list — collect consecutive items
    if (/^[-*+]\s/.test(line)) {
      const items: string[] = []
      while (i < lines.length && /^[-*+]\s/.test(lines[i])) {
        items.push(lines[i].replace(/^[-*+]\s/, ''))
        i++
      }
      nodes.push(
        <ul key={i} style={{ paddingLeft: '20px', margin: '8px 0', display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {items.map((item, j) => (
            <li key={j} style={{ lineHeight: 1.6 }}>{renderInline(item)}</li>
          ))}
        </ul>
      )
      continue
    }

    // Ordered list — collect consecutive items
    if (/^\d+\.\s/.test(line)) {
      const items: string[] = []
      while (i < lines.length && /^\d+\.\s/.test(lines[i])) {
        items.push(lines[i].replace(/^\d+\.\s/, ''))
        i++
      }
      nodes.push(
        <ol key={i} style={{ paddingLeft: '20px', margin: '8px 0', display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {items.map((item, j) => (
            <li key={j} style={{ lineHeight: 1.6 }}>{renderInline(item)}</li>
          ))}
        </ol>
      )
      continue
    }

    // Empty line → spacer
    if (line.trim() === '') {
      nodes.push(<div key={i} style={{ height: '8px' }} />)
      i++
      continue
    }

    // Normal paragraph line
    nodes.push(
      <p key={i} style={{ margin: '4px 0', lineHeight: 1.7 }}>
        {renderInline(line)}
      </p>
    )
    i++
  }

  return <>{nodes}</>
}

// ── Message component ─────────────────────────────────────────────────────────
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
            {isUser ? <User size={13} /> : <Zap size={13} />}
            <span>{isUser ? 'You' : 'CodeGraphRAG'}</span>
          </div>

          {!isUser && message.modelUsed && (
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <span className="badge-model" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                {message.modelUsed.includes('deepseek') ? <Brain size={11} /> : <Bot size={11} />}
                {message.modelUsed.includes('deepseek') ? 'DeepSeek-Coder' : 'Llama 3.3'}
              </span>
              {message.graphNodesCount !== undefined && onInspectGraph && (
                <button
                  onClick={() => onInspectGraph(
                    message.graphNodesCount || 0,
                    message.citations || [],
                    message.modelUsed || ''
                  )}
                  className="btn-ghost"
                  style={{ fontSize: '11px', padding: '2px 8px', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                >
                  <Network size={12} /> {message.graphNodesCount} Graph Nodes
                </button>
              )}
            </div>
          )}
        </div>

        {/* Content — plain text for user, rendered Markdown for assistant */}
        <div style={{ fontSize: '14px', lineHeight: 1.6 }}>
          {isUser
            ? <span style={{ whiteSpace: 'pre-wrap' }}>{message.content}</span>
            : <MarkdownBlock content={message.content} />
          }
        </div>

        {/* Citations list */}
        {message.citations && message.citations.length > 0 && (
          <div style={{ marginTop: '14px', borderTop: '1px solid var(--color-border)', paddingTop: '10px' }}>
            <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-muted)', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Pin size={11} /> GROUNDED CODE CITATIONS ({message.citations.length})
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
              {message.citations.map((cite, i) => (
                <span
                  key={i}
                  className="citation-chip"
                  title="Grounded file reference"
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                >
                  <FileText size={11} /> {cite}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
