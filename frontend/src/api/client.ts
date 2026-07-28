/**
 * api/client.ts
 * -------------
 * Frontend API client for CodeGraphRAG backend endpoints.
 */

const BASE_URL = '/api'

export interface IngestResponse {
  repo_id: string
  status: string
  files_processed: number
  symbols_extracted: number
  chunks_created: number
  message: string
}

export interface QueryResponse {
  query: string
  repo_id: string
  session_id: string
  checkpoint_id: string
  answer: string
  citations: string[]
  model_used: string
  graph_nodes_count: number
  context_chunks_count: number
}

export interface CheckpointInfo {
  checkpoint_id: string
  turn_index: number
  timestamp: string | null
  query_preview: string
}

export interface SessionHistoryResponse {
  session_id: string
  total_turns: number
  checkpoints: CheckpointInfo[]
}

export interface HealthResponse {
  status: string
  app: string
  version: string
  env: string
}

// ── Ingestion ────────────────────────────────────────────────────────────────

export async function ingestGithubRepo(githubUrl: string): Promise<IngestResponse> {
  const res = await fetch(`${BASE_URL}/ingest/github`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ github_url: githubUrl }),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'GitHub ingestion failed')
  }

  return res.json()
}

export async function ingestZipRepo(file: File): Promise<IngestResponse> {
  const formData = new FormData()
  formData.append('file', file)

  const res = await fetch(`${BASE_URL}/ingest/zip`, {
    method: 'POST',
    body: formData,
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'ZIP ingestion failed')
  }

  return res.json()
}

// ── Query ────────────────────────────────────────────────────────────────────

export async function queryCodebase(
  query: string,
  repoId: string,
  useCodeModel: boolean = false,
  sessionId?: string,
): Promise<QueryResponse> {
  const res = await fetch(`${BASE_URL}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query,
      repo_id: repoId,
      use_code_model: useCodeModel,
      session_id: sessionId ?? null,
    }),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Query execution failed')
  }

  return res.json()
}

// ── Session API ───────────────────────────────────────────────────────────────

export async function getSessionHistory(sessionId: string): Promise<SessionHistoryResponse> {
  const res = await fetch(`${BASE_URL}/session/${sessionId}/history`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Failed to fetch session history')
  }
  return res.json()
}

export async function deleteSession(sessionId: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/session/${sessionId}`, { method: 'DELETE' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Failed to delete session')
  }
}

export interface TestCaseResult {
  query: string
  category: string
  retrieval_hit: boolean
  retrieved_files: string[]
  citations_count: number
  has_valid_citations: boolean
  latency_seconds: number
  answer_snippet: string
}

export interface EvaluationMetrics {
  total_queries: number
  retrieval_hit_rate: number
  citation_accuracy: number
  mean_latency_seconds: number
  completed_at: string
  results: TestCaseResult[]
}

export async function runEvaluation(
  repoId: string,
  useCodeModel: boolean = false,
): Promise<EvaluationMetrics> {
  const res = await fetch(`${BASE_URL}/eval/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      repo_id: repoId,
      use_code_model: useCodeModel,
    }),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Evaluation benchmark failed')
  }

  return res.json()
}

// ── Health Check ─────────────────────────────────────────────────────────────

export async function checkHealth(): Promise<HealthResponse> {
  const res = await fetch('/health')
  if (!res.ok) {
    throw new Error('Backend health check failed')
  }
  return res.json()
}
