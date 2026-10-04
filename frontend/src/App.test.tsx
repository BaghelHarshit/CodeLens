import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import App from './App'

const session = { session_id: 'session-1', status: 'created' }
const readyStatus = { session_id: 'session-1', status: 'ready', files_indexed: 2, chunks_created: 4 }

function mockFetch(...responses: object[]) {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async () => {
    const body = responses.shift() ?? {}
    return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })
  })
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('App', () => {
  it('creates a session and uploads a ZIP until ready', async () => {
    mockFetch(session, { session_id: 'session-1', status: 'indexing' }, readyStatus)
    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Create session' }))
    expect(await screen.findByText('Session ready for repository upload.')).toBeInTheDocument()

    const file = new File(['zip'], 'repository.zip', { type: 'application/zip' })
    fireEvent.change(screen.getByLabelText('Repository ZIP or RAR archive'), { target: { files: [file] } })
    fireEvent.click(screen.getByRole('button', { name: 'Upload repository' }))

    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Ready'), { timeout: 3000 })
    expect(screen.getByText('Ask about your repository')).toBeInTheDocument()
    expect(screen.getByText(/Ask a question to see a grounded answer/)).toBeInTheDocument()
  })

  it('asks questions and renders grounded references', async () => {
    mockFetch(
      session,
      { session_id: 'session-1', status: 'indexing' },
      readyStatus,
      {
        answer: 'Authentication is handled in the login function.',
        insufficient_context: false,
        references: [{ relative_path: 'src/auth.ts', symbol_name: 'login', symbol_type: 'function', start_line: 4, end_line: 12 }],
      },
    )
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Create session' }))
    await screen.findByText('Session ready for repository upload.')
    const file = new File(['zip'], 'repository.zip', { type: 'application/zip' })
    fireEvent.change(screen.getByLabelText('Repository ZIP or RAR archive'), { target: { files: [file] } })
    fireEvent.click(screen.getByRole('button', { name: 'Upload repository' }))
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Ready'), { timeout: 3000 })

    fireEvent.change(screen.getByLabelText('Question'), { target: { value: 'Where is authentication handled?' } })
    fireEvent.click(screen.getByRole('button', { name: 'Ask question' }))

    expect(await screen.findByText('Authentication is handled in the login function.')).toBeInTheDocument()
    expect(screen.getByText('src/auth.ts')).toBeInTheDocument()
    expect(screen.getByText(/lines 4–12/)).toBeInTheDocument()
  })

  it('reviews a unified diff and groups findings by severity', async () => {
    mockFetch(
      session,
      { session_id: 'session-1', status: 'indexing' },
      readyStatus,
      {
        outcome: 'findings',
        findings: [
          { severity: 'high', file: 'src/auth.ts', line: 12, issue: 'Missing validation', explanation: 'Input is used before validation.', suggested_fix: 'Validate the input first.', category: 'correctness', confidence: 0.9 },
          { severity: 'low', file: 'src/auth.ts', line: 4, issue: 'Improve naming', explanation: 'The name is unclear.' },
        ],
      },
    )
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Create session' }))
    await screen.findByText('Session ready for repository upload.')
    const file = new File(['zip'], 'repository.zip', { type: 'application/zip' })
    fireEvent.change(screen.getByLabelText('Repository ZIP or RAR archive'), { target: { files: [file] } })
    fireEvent.click(screen.getByRole('button', { name: 'Upload repository' }))
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Ready'), { timeout: 3000 })

    fireEvent.change(screen.getByLabelText('Unified diff'), { target: { value: 'diff --git a/src/auth.ts b/src/auth.ts' } })
    fireEvent.click(screen.getByRole('button', { name: 'Review changes' }))

    expect(await screen.findByText('Missing validation')).toBeInTheDocument()
    expect(screen.getByText('Improve naming')).toBeInTheDocument()
    expect(screen.getByText('Suggested fix:')).toBeInTheDocument()
    expect(screen.getByText('Category: correctness · Confidence: 90%')).toBeInTheDocument()
    expect(screen.getByText('AI suggestions:')).toBeInTheDocument()
  })

  it('shows no-findings review outcome', async () => {
    mockFetch(session, { session_id: 'session-1', status: 'indexing' }, readyStatus, { outcome: 'no_findings', findings: [] })
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Create session' }))
    await screen.findByText('Session ready for repository upload.')
    const file = new File(['zip'], 'repository.zip', { type: 'application/zip' })
    fireEvent.change(screen.getByLabelText('Repository ZIP or RAR archive'), { target: { files: [file] } })
    fireEvent.click(screen.getByRole('button', { name: 'Upload repository' }))
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Ready'), { timeout: 3000 })
    fireEvent.change(screen.getByLabelText('Unified diff'), { target: { value: 'diff --git a/a.py b/a.py' } })
    fireEvent.click(screen.getByRole('button', { name: 'Review changes' }))
    expect(await screen.findByText('No actionable findings were identified in this diff.')).toBeInTheDocument()
  })

  it('rejects an empty review before sending a request', async () => {
    mockFetch(session, { session_id: 'session-1', status: 'indexing' }, readyStatus)
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Create session' }))
    await screen.findByText('Session ready for repository upload.')
    const file = new File(['zip'], 'repository.zip', { type: 'application/zip' })
    fireEvent.change(screen.getByLabelText('Repository ZIP or RAR archive'), { target: { files: [file] } })
    fireEvent.click(screen.getByRole('button', { name: 'Upload repository' }))
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Ready'), { timeout: 3000 })
    expect(screen.getByRole('button', { name: 'Review changes' })).toBeDisabled()
  })

  it('accepts RAR files and rejects unsupported files', async () => {
    mockFetch(session)
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Create session' }))
    await screen.findByText('Session ready for repository upload.')

    const file = new File(['text'], 'notes.txt', { type: 'text/plain' })
    fireEvent.change(screen.getByLabelText('Repository ZIP or RAR archive'), { target: { files: [file] } })

    expect(screen.getByRole('alert')).toHaveTextContent('Choose a ZIP or RAR archive')
    expect(screen.getByRole('button', { name: 'Upload repository' })).toBeDisabled()

    const rar = new File(['rar'], 'repository.rar', { type: 'application/vnd.rar' })
    fireEvent.change(screen.getByLabelText('Repository ZIP or RAR archive'), { target: { files: [rar] } })
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Upload repository' })).not.toBeDisabled()
  })

  it('ends the session and returns to the create state', async () => {
    mockFetch(session, { session_id: 'session-1', status: 'deleted' })
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Create session' }))
    await screen.findByText('Session ready for repository upload.')
    fireEvent.click(screen.getByRole('button', { name: 'End session' }))
    expect(await screen.findByRole('button', { name: 'Create session' })).toBeInTheDocument()
  })

  it('retries failed indexing with a fresh session', async () => {
    mockFetch(
      session,
      { session_id: 'session-1', status: 'indexing' },
      { session_id: 'session-1', status: 'failed', error: 'Indexing failed' },
      { session_id: 'session-1', status: 'deleted' },
      { session_id: 'session-2', status: 'created' },
    )
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Create session' }))
    await screen.findByText('Session ready for repository upload.')
    const file = new File(['zip'], 'repository.zip', { type: 'application/zip' })
    fireEvent.change(screen.getByLabelText('Repository ZIP or RAR archive'), { target: { files: [file] } })
    fireEvent.click(screen.getByRole('button', { name: 'Upload repository' }))
    expect(await screen.findByRole('button', { name: 'Retry with a new session' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Retry with a new session' }))
    expect(await screen.findByText('Session ready for repository upload.')).toBeInTheDocument()
  })
})
