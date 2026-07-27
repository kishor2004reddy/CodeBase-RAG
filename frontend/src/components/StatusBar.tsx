import type { IngestStatus } from '../App'

interface Props {
  status: IngestStatus
  message: string
}

const colors: Record<IngestStatus, string> = {
  idle:    'var(--color-muted)',
  loading: 'var(--color-primary)',
  done:    'var(--color-success)',
  error:   'var(--color-error)',
}

const icons: Record<IngestStatus, string> = {
  idle:    '',
  loading: '⏳',
  done:    '✅',
  error:   '❌',
}

export default function StatusBar({ status, message }: Props) {
  return (
    <div style={{
      padding: '8px 24px',
      background: 'var(--color-bg)',
      borderBottom: '1px solid var(--color-border)',
      display: 'flex',
      alignItems: 'center',
      gap: '8px',
      fontSize: '13px',
      color: colors[status],
    }}>
      <span>{icons[status]}</span>
      <span>{message}</span>
      {status === 'loading' && (
        <span style={{
          display: 'inline-block',
          width: '8px',
          height: '8px',
          borderRadius: '50%',
          background: 'var(--color-primary)',
          animation: 'pulse 1s ease-in-out infinite',
        }} />
      )}
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
      `}</style>
    </div>
  )
}
