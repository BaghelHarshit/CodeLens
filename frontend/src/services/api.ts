import type { ApiErrorPayload, IndexingStatus, SessionResponse, UploadResponse } from '../types'

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

async function request<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(input, init)
  } catch {
    throw new ApiError(0, 'NETWORK_ERROR', 'The CodeLens service could not be reached.')
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

export function getIndexingStatus(sessionId: string): Promise<IndexingStatus> {
  return request<IndexingStatus>(`${API_BASE_URL}/api/session/${sessionId}/status`)
}

export async function deleteSession(sessionId: string): Promise<SessionResponse> {
  return request<SessionResponse>(`${API_BASE_URL}/api/session/${sessionId}`, { method: 'DELETE' })
}
