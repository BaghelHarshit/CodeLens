import { useCallback, useEffect, useRef, useState } from 'react'

import './App.css'
import { ApiError, askQuestion, createSession, deleteSession, getIndexingStatus, submitReview, uploadRepository } from './services/api'
import type { ChatResponse, IndexingStatus, ReviewFinding, ReviewResponse, ReviewSeverity, ReviewSource, SessionStatus, UploadResponse } from './types'

const POLL_INTERVAL_MS = 1000
const MAX_REVIEW_DIFF_CHARS = 200_000
const REVIEW_SEVERITIES: ReviewSeverity[] = ['critical', 'high', 'medium', 'low', 'info']

function statusLabel(status: SessionStatus): string {
  return status === 'ready' ? 'Ready' : status.charAt(0).toUpperCase() + status.slice(1)
}

function App() {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [status, setStatus] = useState<SessionStatus>('created')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [summary, setSummary] = useState<IndexingStatus | UploadResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [question, setQuestion] = useState('')
  const [answers, setAnswers] = useState<Array<{ question: string; response: ChatResponse }>>([])
  const [chatError, setChatError] = useState<string | null>(null)
  const [asking, setAsking] = useState(false)
  const [reviewDiff, setReviewDiff] = useState('')
  const [reviewSource, setReviewSource] = useState<ReviewSource>('manual')
  const [reviewResult, setReviewResult] = useState<ReviewResponse | null>(null)
  const [reviewError, setReviewError] = useState<string | null>(null)
  const [reviewing, setReviewing] = useState(false)
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

  function clearChat() {
    setQuestion('')
    setAnswers([])
    setChatError(null)
  }

  function clearReview() {
    setReviewDiff('')
    setReviewResult(null)
    setReviewError(null)
  }

  async function handleReview() {
    const trimmed = reviewDiff.trim()
    if (!sessionId || status !== 'ready' || reviewing) return
    if (reviewSource === 'manual' && !trimmed) {
      setReviewError('Paste a unified diff to review.')
      setReviewResult(null)
      return
    }
    if (reviewSource === 'manual' && trimmed.length > MAX_REVIEW_DIFF_CHARS) {
      setReviewError(`The diff must be ${MAX_REVIEW_DIFF_CHARS.toLocaleString()} characters or fewer.`)
      setReviewResult(null)
      return
    }
    setReviewing(true)
    setReviewError(null)
    setReviewResult(null)
    try {
      setReviewResult(await submitReview(sessionId, reviewSource, reviewSource === 'manual' ? trimmed : undefined))
    } catch (cause) {
      setReviewError(cause instanceof ApiError ? cause.message : 'The code review could not be completed.')
    } finally {
      setReviewing(false)
    }
  }

  function findingsBySeverity(findings: ReviewFinding[], severity: ReviewSeverity) {
    return findings.filter((finding) => finding.severity === severity)
  }

  async function handleCreate() {
    setBusy(true)
    setError(null)
    clearChat()
    clearReview()
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

  async function handleAsk() {
    const trimmed = question.trim()
    if (!sessionId || status !== 'ready' || !trimmed || asking) return
    setAsking(true)
    setChatError(null)
    try {
      const response = await askQuestion(sessionId, trimmed)
      setAnswers((current) => [...current, { question: trimmed, response }])
      setQuestion('')
    } catch (cause) {
      setChatError(cause instanceof ApiError ? cause.message : 'The question could not be answered.')
    } finally {
      setAsking(false)
    }
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
      clearChat()
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
        {hasSession && status === 'failed' && (
          <p className="muted feature-gate">Q&amp;A is unavailable until the repository finishes indexing.</p>
        )}
        {hasSession && status === 'ready' && (
          <div>
          <section className="qa-panel" aria-labelledby="qa-heading">

            <div>
              <h2 id="qa-heading">Ask about your repository</h2>
              <p className="muted">Answers are grounded in the indexed repository and include supporting references.</p>
            </div>
            <form className="question-form" onSubmit={(event) => { event.preventDefault(); void handleAsk() }}>
              <label htmlFor="repository-question">Question</label>
              <textarea
                id="repository-question"
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="Where is authentication handled?"
                rows={3}
                maxLength={4000}
                disabled={asking}
              />
              <div className="question-actions">
                <span className="muted">{question.length}/4000</span>
                <button type="submit" disabled={asking || !question.trim()}>
                  {asking ? 'Thinking…' : 'Ask question'}
                </button>
              </div>
            </form>
            {asking && <p className="muted" role="status">Searching the repository…</p>}
            {chatError && <p className="error-message" role="alert">{chatError}</p>}
            {answers.length === 0 && !asking && <p className="muted qa-empty">Ask a question to see a grounded answer.</p>}
            <div className="answer-list">
              {answers.map(({ question: askedQuestion, response }, index) => (
                <article className="answer-card" key={`${askedQuestion}-${index}`}>
                  <h3>{askedQuestion}</h3>
                  <p className="answer-text">{response.answer}</p>
                  {response.insufficient_context && <p className="muted">There was not enough repository context to provide a grounded answer.</p>}
                  {response.references.length > 0 && (
                    <div>
                      <h4>References</h4>
                      <ul className="reference-list">
                        {response.references.map((reference, referenceIndex) => (
                          <li key={`${reference.relative_path}-${reference.start_line ?? 'na'}-${referenceIndex}`}>
                            <strong>{reference.relative_path}</strong>
                            {reference.symbol_name && <span> · {reference.symbol_name}</span>}
                            {reference.symbol_type && <span> ({reference.symbol_type})</span>}
                            {(reference.start_line || reference.end_line) && (
                              <span> · lines {reference.start_line ?? '?'}–{reference.end_line ?? reference.start_line ?? '?'}</span>
                            )}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </article>
              ))}
            </div>
          </section>
          <section className="review-panel" aria-labelledby="review-heading">
            <div>
              <h2 id="review-heading">Review code changes</h2>
              <p className="muted">Choose a manual diff or review the latest commit from the uploaded Git repository.</p>
            </div>
            <p className="review-notice"><strong>AI suggestions:</strong> findings are advisory. CodeLens never modifies your code automatically.</p>
            <fieldset className="review-source">
              <legend>Review source</legend>
              <label><input type="radio" name="review-source" value="manual" checked={reviewSource === 'manual'} onChange={() => setReviewSource('manual')} disabled={reviewing} /> Manual unified diff</label>
              <label><input type="radio" name="review-source" value="last_commit" checked={reviewSource === 'last_commit'} onChange={() => setReviewSource('last_commit')} disabled={reviewing} /> Latest Git commit</label>
              {reviewSource === 'last_commit' && <p className="muted">The uploaded repository must include Git metadata. CodeLens reads the latest commit without modifying the repository.</p>}
            </fieldset>
            <form className="review-form" onSubmit={(event) => { event.preventDefault(); void handleReview() }}>
              <label htmlFor="review-diff">Unified diff</label>
              <textarea
                id="review-diff"
                value={reviewDiff}
                onChange={(event) => { setReviewDiff(event.target.value); setReviewError(null) }}
                placeholder={'diff --git a/src/app.py b/src/app.py\n+++ b/src/app.py\n@@ -1 +1 @@'}
                rows={8}
                maxLength={MAX_REVIEW_DIFF_CHARS + 1}
                disabled={reviewing || reviewSource !== 'manual'}
              />
              <div className="question-actions">
                <span className="muted">{reviewSource === 'manual' ? `${reviewDiff.length.toLocaleString()}/${MAX_REVIEW_DIFF_CHARS.toLocaleString()}` : 'Latest commit selected'}</span>
                <button type="submit" disabled={reviewing || (reviewSource === 'manual' && !reviewDiff.trim())}>{reviewing ? 'Reviewing…' : 'Review changes'}</button>
              </div>
            </form>
            {reviewing && <p className="muted" role="status">Analyzing changed code and repository context…</p>}
            {reviewError && <p className="error-message" role="alert">{reviewError}</p>}
            {reviewResult?.outcome === 'no_findings' && <p className="success-message">No actionable findings were identified in this diff.</p>}
            {reviewResult?.outcome === 'insufficient_context' && <p className="muted review-empty">There was not enough indexed repository context to ground this review.</p>}
            {reviewResult?.outcome === 'findings' && (
              <div className="finding-list">
                {REVIEW_SEVERITIES.map((severity) => {
                  const findings = findingsBySeverity(reviewResult.findings, severity)
                  if (findings.length === 0) return null
                  return (
                    <section className="severity-group" key={severity} aria-labelledby={`severity-${severity}`}>
                      <h3 id={`severity-${severity}`}><span className={`severity-badge severity-${severity}`}>{severity}</span> {findings.length} finding{findings.length === 1 ? '' : 's'}</h3>
                      {findings.map((finding, index) => (
                        <article className="finding-card" key={`${finding.file}-${finding.line}-${index}`}>
                          <h4>{finding.issue}</h4>
                          <p className="finding-location"><strong>{finding.file}</strong> · line {finding.line}</p>
                          <p>{finding.explanation}</p>
                          {finding.suggested_fix && <p><strong>Suggested fix:</strong> {finding.suggested_fix}</p>}
                          {(finding.category || finding.confidence !== null && finding.confidence !== undefined) && (
                            <p className="muted finding-meta">
                              {finding.category && <>Category: {finding.category}</>}
                              {finding.category && finding.confidence !== null && finding.confidence !== undefined && ' · '}
                              {finding.confidence !== null && finding.confidence !== undefined && `Confidence: ${Math.round(finding.confidence * 100)}%`}
                            </p>
                          )}
                        </article>
                      ))}
                    </section>
                  )
                })}
              </div>
            )}
          </section>
          </div>
        )}
      </section>
    </main>
  )
}

export default App
