/**
 * components/GraphDrawer.tsx
 * --------------------------
 * Interactive slide-out drawer showing structural graph relationships
 * (CALLS, IMPORTS, INHERITS) retrieved from Neo4j for a query.
 */

import { Network, X, Bot, FileText, Pin } from 'lucide-react'

interface Props {
  isOpen: boolean
  onClose: () => void
  graphCount: number
  citations: string[]
  modelUsed: string
}

export default function GraphDrawer({
  isOpen,
  onClose,
  graphCount,
  citations,
  modelUsed,
}: Props) {
  if (!isOpen) return null

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      zIndex: 100,
      display: 'flex',
      justifyContent: 'flex-end',
      background: 'rgba(0, 0, 0, 0.5)',
      backdropFilter: 'blur(3px)',
    }}>
      <div style={{
        width: '420px',
        maxWidth: '90vw',
        height: '100%',
        background: 'var(--color-surface)',
        borderLeft: '1px solid var(--color-border)',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '-4px 0 20px rgba(0, 0, 0, 0.4)',
      }}>
        {/* Header */}
        <div style={{
          padding: '16px 20px',
          borderBottom: '1px solid var(--color-border)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}>
          <h3 style={{ fontSize: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Network size={16} /> Query Retrieval Details
          </h3>
          <button
            onClick={onClose}
            className="btn-ghost"
            style={{ padding: '4px 10px', fontSize: '13px', display: 'inline-flex', alignItems: 'center', gap: '5px' }}
          >
            <X size={13} /> Close
          </button>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '20px' }}>
          {/* Metadata badges */}
          <div style={{ marginBottom: '20px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div className="info-card">
              <span className="info-label" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}><Bot size={12} /> LLM Model:</span>
              <span className="info-val">{modelUsed || 'llama-3.3-70b-versatile'}</span>
            </div>
            <div className="info-card">
              <span className="info-label" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}><Network size={12} /> Neo4j Graph Nodes Expanded:</span>
              <span className="info-val">{graphCount} dependency nodes</span>
            </div>
            <div className="info-card">
              <span className="info-label" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}><FileText size={12} /> Grounded Citations:</span>
              <span className="info-val">{citations.length} files cited</span>
            </div>
          </div>

          {/* Citations List */}
          <h4 style={{ fontSize: '14px', marginBottom: '10px', color: 'var(--color-text)' }}>
            Source File References
          </h4>
          {citations.length === 0 ? (
            <div style={{ fontSize: '13px', color: 'var(--color-muted)' }}>
              No specific line citations generated.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {citations.map((cite, idx) => (
                <div
                  key={idx}
                  style={{
                    padding: '8px 12px',
                    background: 'var(--color-bg)',
                    border: '1px solid var(--color-border)',
                    borderRadius: 'var(--radius-sm)',
                    fontFamily: 'var(--font-mono)',
                    fontSize: '12px',
                    color: 'var(--color-primary)',
                    wordBreak: 'break-all',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                  }}
                >
                  <Pin size={12} /> {cite}
                </div>
              ))}
            </div>
          )}

          {/* Structure Info */}
          <div style={{ marginTop: '24px', padding: '14px', background: 'var(--color-bg)', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)' }}>
            <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-muted)', marginBottom: '6px' }}>
              HOW GRAPH EXPANSION WORKS
            </div>
            <div style={{ fontSize: '13px', color: 'var(--color-text)', lineHeight: '1.5' }}>
              CodeGraphRAG executes 1-2 hop Cypher traversals in Neo4j starting from seed vector search symbols, pulling in connected <code>CALLS</code>, <code>IMPORTS</code>, and <code>INHERITS</code> edges to form grounded architecture context.
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
