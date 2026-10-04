import type { ApiErrorPayload, ChatResponse, IndexingStatus, SessionResponse, UploadResponse } from '../types'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000').replace(/\/$/, '')

export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

const REQUEST_TIMEOUT_MS = 10_000

async function request<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
  let response: Response
  try {
    response = await fetch(input, { ...init, signal: init?.signal ?? controller.signal })
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') {
      throw new ApiError(0, 'NETWORK_TIMEOUT', 'The CodeLens service did not respond in time.')
    }
    throw new ApiError(0, 'NETWORK_ERROR', 'The CodeLens service could not be reached.')
  } finally {
    window.clearTimeout(timeout)
  }
  if (!response.ok) {
    let payload: ApiErrorPayload = {}
    try {
      payload = (await response.json()) as ApiErrorPayload
    } catch {
      // Keep the public error generic when the server response is not JSON.
    }
    throw new ApiError(
      response.status,
      payload.error?.code ?? 'REQUEST_FAILED',
      payload.error?.message ?? 'The request could not be completed.',
    )
  }
  return (await response.json()) as T
}

export function createSession(): Promise<SessionResponse> {
  return request<SessionResponse>(`${API_BASE_URL}/api/session`, { method: 'POST' })
}

export function uploadRepository(sessionId: string, file: File): Promise<UploadResponse> {
  const form = new FormData()
  form.append('repository', file)
  return request<UploadResponse>(`${API_BASE_URL}/api/session/${sessionId}/repository`, {
    method: 'POST',
    body: form,
  })
}

export function askQuestion(sessionId: string, question: string): Promise<ChatResponse> {
  return request<ChatResponse>(`${API_BASE_URL}/api/session/${sessionId}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })
}

export async function getIndexingStatus(sessionId: string): Promise<IndexingStatus> {
  const response = await request<{
    session_id: string
    state?: IndexingStatus['status']
    status?: IndexingStatus['status']
    progress?: number
    files_seen?: number
    files_discovered?: number
    files_indexed?: number
    chunks_created?: number
    chunks_indexed?: number
    skipped_files?: number
    files_skipped?: number
    warnings?: string[]
    error_message?: string | null
    error?: string
  }>(`${API_BASE_URL}/api/session/${sessionId}/status`)

  return {
    session_id: response.session_id,
    status: response.status ?? response.state ?? 'failed',
    progress: response.progress,
    files_seen: response.files_seen,
    files_indexed: response.files_indexed ?? response.files_discovered,
    files_skipped: response.files_skipped ?? response.skipped_files,
    chunks_created: response.chunks_created ?? response.chunks_indexed,
    warnings: response.warnings,
    error: response.error ?? response.error_message ?? undefined,
  }
}

export async function deleteSession(sessionId: string): Promise<SessionResponse> {
  return request<SessionResponse>(`${API_BASE_URL}/api/session/${sessionId}`, { method: 'DELETE' })
}
