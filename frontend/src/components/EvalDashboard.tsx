import { useState } from 'react'
import { runEvaluation, type EvaluationMetrics } from '../api/client'

interface Props {
  isOpen: boolean
  onClose: () => void
  activeRepoId: string | null
}

export default function EvalDashboard({ isOpen, onClose, activeRepoId }: Props) {
  const [metrics, setMetrics] = useState<EvaluationMetrics | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!isOpen) return null

  const handleRunBenchmark = async () => {
    if (!activeRepoId || loading) return
    setLoading(true)
    setError(null)

    try {
      const data = await runEvaluation(activeRepoId)
      setMetrics(data)
    } catch (err: any) {
      setError(err.message || 'Benchmark execution failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      zIndex: 100,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'rgba(0, 0, 0, 0.6)',
      backdropFilter: 'blur(4px)',
    }}>
      <div style={{
        width: '680px',
        maxWidth: '92vw',
        maxHeight: '85vh',
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-lg)',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 10px 40px rgba(0, 0, 0, 0.5)',
        overflow: 'hidden',
      }}>
        {/* Header */}
        <div style={{
          padding: '18px 24px',
          borderBottom: '1px solid var(--color-border)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}>
          <div>
            <h3 style={{ fontSize: '17px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              📊 Evaluation & Observability Suite
            </h3>
            <div style={{ fontSize: '12px', color: 'var(--color-muted)', marginTop: '2px' }}>
              Benchmark CodeGraphRAG retrieval accuracy, citation precision, and query latency
            </div>
          </div>
          <button onClick={onClose} className="btn-ghost" style={{ padding: '4px 10px' }}>
            ✕ Close
          </button>
        </div>

        {/* Content */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '24px' }}>
          {!activeRepoId ? (
            <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--color-muted)' }}>
              ⚠️ Please index a repository first to run evaluation benchmarks.
            </div>
          ) : (
            <>
              {/* Trigger bar */}
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '14px 18px',
                background: 'var(--color-bg)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--color-border)',
                marginBottom: '20px',
              }}>
                <div>
                  <div style={{ fontSize: '14px', fontWeight: 600 }}>
                    Target Repository: <span style={{ color: 'var(--color-primary)' }}>{activeRepoId}</span>
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--color-muted)' }}>
                    Runs standardized query benchmark across vector and graph search components.
                  </div>
                </div>
                <button
                  onClick={handleRunBenchmark}
                  className="btn-primary"
                  disabled={loading}
                >
                  {loading ? 'Running Suite...' : '🚀 Run Benchmark'}
                </button>
              </div>

              {error && (
                <div style={{
                  padding: '12px 16px',
                  background: 'rgba(248, 113, 113, 0.1)',
                  border: '1px solid var(--color-error)',
                  color: 'var(--color-error)',
                  borderRadius: 'var(--radius-sm)',
                  marginBottom: '20px',
                  fontSize: '13px',
                }}>
                  ❌ {error}
                </div>
              )}

              {/* Metric Cards */}
              {metrics && (
                <>
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(3, 1fr)',
                    gap: '12px',
                    marginBottom: '24px',
                  }}>
                    <div className="eval-metric-card">
                      <div className="eval-metric-label">Retrieval Hit Rate</div>
                      <div className="eval-metric-val" style={{ color: 'var(--color-success)' }}>
                        {(metrics.retrieval_hit_rate * 100).toFixed(0)}%
                      </div>
                      <div className="eval-metric-sub">Vector + Neo4j Graph match</div>
                    </div>

                    <div className="eval-metric-card">
                      <div className="eval-metric-label">Citation Precision</div>
                      <div className="eval-metric-val" style={{ color: 'var(--color-primary)' }}>
                        {(metrics.citation_accuracy * 100).toFixed(0)}%
                      </div>
                      <div className="eval-metric-sub">Grounded source citations</div>
                    </div>

                    <div className="eval-metric-card">
                      <div className="eval-metric-label">Mean Latency</div>
                      <div className="eval-metric-val" style={{ color: '#f59e0b' }}>
                        {metrics.mean_latency_seconds}s
                      </div>
                      <div className="eval-metric-sub">Average query response time</div>
                    </div>
                  </div>

                  {/* Benchmark Test Cases Detail Table */}
                  <h4 style={{ fontSize: '14px', marginBottom: '12px' }}>
                    Benchmark Test Suite Results ({metrics.results.length} cases)
                  </h4>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    {metrics.results.map((res, idx) => (
                      <div
                        key={idx}
                        style={{
                          padding: '12px 16px',
                          background: 'var(--color-bg)',
                          border: '1px solid var(--color-border)',
                          borderRadius: 'var(--radius-sm)',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                          <span style={{ fontSize: '13px', fontWeight: 600 }}>
                            {idx + 1}. {res.query}
                          </span>
                          <span style={{
                            fontSize: '11px',
                            padding: '2px 6px',
                            borderRadius: '4px',
                            background: res.retrieval_hit ? 'rgba(52, 211, 153, 0.15)' : 'rgba(248, 113, 113, 0.15)',
                            color: res.retrieval_hit ? 'var(--color-success)' : 'var(--color-error)',
                            fontWeight: 600,
                          }}>
                            {res.retrieval_hit ? 'HIT' : 'MISS'}
                          </span>
                        </div>
                        <div style={{ fontSize: '12px', color: 'var(--color-muted)', display: 'flex', gap: '16px' }}>
                          <span>Category: <code>{res.category}</code></span>
                          <span>Citations: {res.citations_count}</span>
                          <span>Latency: {res.latency_seconds}s</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
