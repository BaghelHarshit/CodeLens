import { useCallback, useEffect, useRef, useState } from 'react'

import './App.css'
import { ApiError, createSession, deleteSession, getIndexingStatus, uploadRepository } from './services/api'
import type { IndexingStatus, SessionStatus, UploadResponse } from './types'

const POLL_INTERVAL_MS = 1000

function statusLabel(status: SessionStatus): string {
  return status === 'ready' ? 'Ready' : status.charAt(0).toUpperCase() + status.slice(1)
}

function App() {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [status, setStatus] = useState<SessionStatus>('created')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [summary, setSummary] = useState<IndexingStatus | UploadResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const pollingRef = useRef<number | null>(null)
  const pollStatusRef = useRef<(id: string) => Promise<void>>(() => Promise.resolve())

  const stopPolling = useCallback(() => {
    if (pollingRef.current !== null) {
      window.clearTimeout(pollingRef.current)
      pollingRef.current = null
    }
  }, [])

  const pollStatus = useCallback(
    async (id: string) => {
      try {
        const next = await getIndexingStatus(id)
        setStatus(next.status)
        setSummary(next)
        if (next.status === 'indexing' || next.status === 'uploading') {
          pollingRef.current = window.setTimeout(() => void pollStatusRef.current(id), POLL_INTERVAL_MS)
        } else if (next.status === 'failed') {
          setError(next.error ?? 'Indexing failed. You can end this session and try again.')
        }
      } catch (cause) {
        setError(cause instanceof ApiError ? cause.message : 'Indexing status could not be loaded.')
        stopPolling()
      }
    },
    [stopPolling],
  )
  useEffect(() => {
    pollStatusRef.current = pollStatus
  }, [pollStatus])
  useEffect(() => () => stopPolling(), [stopPolling])

  async function handleCreate() {
    setBusy(true)
    setError(null)
    try {
      const session = await createSession()
      setSessionId(session.session_id)
      setStatus(session.status)
      setSummary(null)
      setSelectedFile(null)
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'A session could not be created.')
    } finally {
      setBusy(false)
    }
  }

  function handleFileChange(file: File | undefined) {
    setError(null)
    if (!file) {
      setSelectedFile(null)
      return
    }
    const filename = file.name.toLowerCase()
    if (!filename.endsWith('.zip') && !filename.endsWith('.rar')) {
      setSelectedFile(null)
      setError('Choose a ZIP or RAR archive to upload.')
      return
    }
    setSelectedFile(file)
  }

  async function handleUpload() {
    if (!sessionId || !selectedFile) return
    setBusy(true)
    setError(null)
    stopPolling()
    setStatus('uploading')
    try {
      const result = await uploadRepository(sessionId, selectedFile)
      setSummary(result)
      setStatus(result.status)
      setSelectedFile(null)
      if (result.status === 'indexing') void pollStatus(sessionId)
    } catch (cause) {
      setStatus('failed')
      setError(cause instanceof ApiError ? cause.message : 'The repository could not be uploaded.')
    } finally {
      setBusy(false)
    }
  }

  async function handleDelete() {
    if (!sessionId) return
    setBusy(true)
    setError(null)
    stopPolling()
    try {
      await deleteSession(sessionId)
      setSessionId(null)
      setStatus('created')
      setSummary(null)
      setSelectedFile(null)
    } catch (cause) {
      if (cause instanceof ApiError && (cause.status === 404 || cause.status === 410)) {
        setSessionId(null)
        setStatus('created')
      } else {
        setError(cause instanceof ApiError ? cause.message : 'The session could not be ended.')
      }
    } finally {
      setBusy(false)
    }
  }

  async function handleRetry() {
    if (!sessionId) return
    setBusy(true)
    setError(null)
    stopPolling()
    try {
      try {
        await deleteSession(sessionId)
      } catch (cause) {
        if (!(cause instanceof ApiError) || (cause.status !== 404 && cause.status !== 410)) throw cause
      }
      const session = await createSession()
      setSessionId(session.session_id)
      setStatus(session.status)
      setSummary(null)
      setSelectedFile(null)
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'A new session could not be created.')
    } finally {
      setBusy(false)
    }
  }

  const hasSession = sessionId !== null
  const statusText = hasSession ? statusLabel(status) : 'No active session'

  return (
    <main className="app-shell">
      <header className="app-header">
        <p className="eyebrow">Repository intelligence</p>
        <h1>CodeLens</h1>
        <p className="intro">
          Upload a local repository to understand its code and review changes with grounded context.
        </p>
      </header>

      <section className="workspace-card" aria-labelledby="workspace-heading">
        <div className="card-heading">
          <div>
            <h2 id="workspace-heading">Start a temporary session</h2>
            <p className="muted">Your repository is used only for this temporary analysis session.</p>
          </div>
          <span className={`status-pill status-${status}`} role="status">{statusText}</span>
        </div>

        {!hasSession ? (
          <button type="button" onClick={() => void handleCreate()} disabled={busy}>
            {busy ? 'Creating…' : 'Create session'}
          </button>
        ) : (
          <>
            <p className="session-id">Session ready for repository upload.</p>
            <label className="file-picker" htmlFor="repository-file">
              <span>Repository ZIP or RAR archive</span>
              <input
                id="repository-file"
                type="file"
                accept=".zip,.rar,application/zip,application/vnd.rar,application/x-rar-compressed"
                onChange={(event) => handleFileChange(event.target.files?.[0])}
                disabled={busy || status !== 'created'}
              />
            </label>
            {selectedFile && <p className="file-name">Selected: {selectedFile.name}</p>}
            <div className="action-row">
              <button type="button" onClick={() => void handleUpload()} disabled={busy || !selectedFile || status !== 'created'}>
                {busy ? 'Uploading…' : 'Upload repository'}
              </button>
              <button className="secondary-button" type="button" onClick={() => void handleDelete()} disabled={busy}>
                End session
              </button>
              {status === 'failed' && (
                <button className="secondary-button" type="button" onClick={() => void handleRetry()} disabled={busy}>
                  Retry with a new session
                </button>
              )}
            </div>
          </>
        )}

        {summary && (
          <div className="progress-panel" aria-label="Indexing progress">
            <strong>{statusText}</strong>
            {'progress' in summary && typeof summary.progress === 'number' && (
              <progress max="1" value={summary.progress} />
            )}
            <p className="muted">
              {'files_indexed' in summary && summary.files_indexed !== undefined
                ? `${summary.files_indexed} files indexed`
                : 'Preparing repository index…'}
            </p>
            {summary.warnings && summary.warnings.length > 0 && (
              <ul className="warning-list">{summary.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
            )}
          </div>
        )}

        {error && <p className="error-message" role="alert">{error}</p>}
        {!hasSession && <p className="muted feature-gate">Q&amp;A and code review become available after indexing a repository.</p>}
        {hasSession && status !== 'ready' && status !== 'failed' && (
          <p className="muted feature-gate">Q&amp;A and code review are available when indexing reaches Ready.</p>
        )}
        {hasSession && status === 'ready' && (
          <p className="success-message">Repository ready. Q&amp;A and code review controls will appear in the next workflow tickets.</p>
        )}
      </section>
    </main>
  )
}

export default App
