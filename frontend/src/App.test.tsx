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
    expect(screen.getByText(/Repository ready/)).toBeInTheDocument()
    expect(screen.getByText(/Q&A and code review controls/)).toBeInTheDocument()
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
