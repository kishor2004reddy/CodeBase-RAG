import type { IngestStatus } from '../App'

const BASE_URL = '/api'

// ── Ingestion ────────────────────────────────────────────────────────────────

export async function ingestRepo(
  repoUrl: string,
  onStatusChange: (status: IngestStatus, message: string) => void,
): Promise<void> {
  // Start ingestion job
  const res = await fetch(`${BASE_URL}/ingest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo_url: repoUrl }),
  })

  if (!res.ok) {
    throw new Error(`Ingestion failed: ${res.statusText}`)
  }

  const { job_id } = await res.json()
  onStatusChange('loading', 'Cloning repository...')

  // Poll for progress
  await pollIngestStatus(job_id, onStatusChange)
}

async function pollIngestStatus(
  jobId: string,
  onStatusChange: (status: IngestStatus, message: string) => void,
): Promise<void> {
  const maxAttempts = 120   // 2 minutes max (polling every second)
  let attempts = 0

  while (attempts < maxAttempts) {
    await delay(2000)
    attempts++

    const res = await fetch(`${BASE_URL}/ingest/status/${jobId}`)
    if (!res.ok) continue

    const data = await res.json()

    onStatusChange('loading', data.message ?? 'Processing...')

    if (data.status === 'done') {
      onStatusChange('done', `✅ Indexed ${data.chunks ?? ''} chunks from ${data.files ?? ''} files.`)
      return
    }

    if (data.status === 'error') {
      onStatusChange('error', data.message ?? 'Ingestion failed.')
      throw new Error(data.message)
    }
  }

  onStatusChange('error', 'Ingestion timed out. Try a smaller repository.')
  throw new Error('Timeout')
}

// ── Query ────────────────────────────────────────────────────────────────────

export interface QueryResult {
  answer: string
  citations: string[]
}

export async function queryRepo(question: string): Promise<QueryResult> {
  const res = await fetch(`${BASE_URL}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })

  if (!res.ok) {
    throw new Error(`Query failed: ${res.statusText}`)
  }

  return res.json()
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function delay(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}
