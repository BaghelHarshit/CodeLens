export type SessionStatus = 'created' | 'uploading' | 'indexing' | 'ready' | 'failed' | 'deleted'

export interface SessionResponse {
  session_id: string
  status: SessionStatus
}

export interface UploadResponse {
  session_id: string
  status: SessionStatus
  message: string
  files_accepted?: number
  files_skipped?: number
  extracted_bytes?: number
  warnings?: string[]
}

export interface IndexingStatus {
  session_id: string
  status: SessionStatus
  progress?: number
  files_seen?: number
  files_indexed?: number
  files_skipped?: number
  chunks_created?: number
  warnings?: string[]
  error?: string
}

export interface ApiErrorPayload {
  error?: { code?: string; message?: string }
}
