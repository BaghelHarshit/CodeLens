# CodeLens V1 API Contract

This document defines the local-repository input contract for TICKET-002. It is a frontend/backend contract; implementation is delivered by later tickets.

## Repository input

V1 accepts a repository as a ZIP archive uploaded from the user's local machine. The browser must not send an arbitrary server filesystem path. A client submits the archive as `multipart/form-data`:

```http
POST /api/session/{session_id}/repository
Content-Type: multipart/form-data

repository=<repository.zip>
```

The upload field is named `repository`. The filename is informational only and must not determine the destination path. Accepted files have a `.zip` extension and the `application/zip` or `application/octet-stream` content type. The server validates the archive contents rather than trusting the content type.

### V1 limits

The following defaults bound resource use. They are configuration values, not promises that the current implementation already enforces them:

| Limit | Default |
| --- | ---: |
| Compressed upload size | 100 MiB |
| Extracted repository size | 500 MiB |
| Extracted file count | 10,000 |
| Individual extracted file size | 10 MiB |
| Archive nesting/path length | 100 path segments / 512 characters |

The backend may expose these values through configuration, but it must never allow a request to bypass them. A later implementation ticket may tune defaults after testing.

## Safe archive handling

The server treats every archive as untrusted data:

- Reject an invalid or corrupt ZIP, an empty archive, and an archive containing no usable files.
- Normalize member names to relative POSIX paths before writing them.
- Reject absolute paths, `..` traversal, NUL bytes, path collisions, and paths that resolve outside the session's repository directory.
- Reject symbolic links and unsupported special entries; only regular files and directories are accepted.
- Enforce compressed, extracted-byte, file-count, individual-file, and path-length limits while extracting.
- Do not follow links, run scripts/hooks/builds, import modules, or otherwise execute repository content.
- Do not expose server absolute paths in responses or logs.

A failed validation must leave no partially accepted repository available for indexing. The implementation should clean up any temporary extraction area before returning the error.

## Repository filtering

Ingestion preserves source files for indexing but does not promise that every archive member becomes an embedding. The later discovery stage ignores `.git/` and common generated/dependency/cache/vendor directories (for example `node_modules/`, `.venv/`, `dist/`, `build/`, `coverage/`, and `__pycache__/`). It also skips binary, oversized, and unsupported file types. Skips are reported as warnings/counts and do not fail an otherwise valid repository.

## Session and indexing states

A session is created independently through `POST /api/session`. Repository/indexing state uses these values:

```text
created → uploading → indexing → ready
                    └──────────→ failed
ready   → deleted
failed  → deleted
created → deleted
```

- `created`: session exists but no repository upload has started.
- `uploading`: the repository request is being validated or received.
- `indexing`: safe repository data is available and indexing is in progress.
- `ready`: the shared repository index is available for Q&A and review.
- `failed`: the current upload/index attempt failed; the response/status includes a safe error code and message.
- `deleted`: temporary repository, metadata, and index data have been removed.

Q&A and code review are allowed only in `ready`. Repository replacement is not supported in the first implementation; a client must delete the session and create a new one. Status polling will use a later endpoint, conventionally `GET /api/session/{session_id}/status`, until indexing reaches `ready` or `failed`.

## Responses

A successful upload starts indexing and returns a status summary. The exact progress fields may grow, but these fields are stable for the initial contract:

```json
{
  "session_id": "abc123",
  "status": "indexing",
  "message": "Repository accepted; indexing started"
}
```

A status response uses the same `session_id` and `status`, and may include `progress`, `files_seen`, `files_indexed`, `files_skipped`, `chunks_created`, `warnings`, and `error`.

## Errors

Errors use JSON and must not disclose absolute filesystem paths or secrets:

```json
{
  "error": {
    "code": "INVALID_ARCHIVE",
    "message": "The uploaded file is not a valid ZIP archive."
  }
}
```

Initial error codes include:

| Code | Meaning |
| --- | --- |
| `SESSION_NOT_FOUND` | The session ID does not exist. |
| `SESSION_DELETED` | The session has already been deleted. |
| `INVALID_SESSION_STATE` | The requested operation is not valid for the current state. |
| `MISSING_REPOSITORY` | The multipart request has no `repository` field. |
| `UNSUPPORTED_ARCHIVE` | The upload is not a supported ZIP input. |
| `UPLOAD_TOO_LARGE` | The compressed upload exceeds its limit. |
| `INVALID_ARCHIVE` | The archive is corrupt, empty, or unsafe. |
| `EXTRACTION_LIMIT_EXCEEDED` | Extracted bytes, files, path length, or nesting exceed a limit. |
| `EMPTY_REPOSITORY` | No usable repository files remain after validation/filtering. |
| `INDEXING_FAILED` | A fatal indexing/provider failure occurred. |

HTTP status codes should be conventional: `400` for malformed input, `404` for an unknown session, `409` for an invalid lifecycle state, `413` for size limits, and `500`/`503` for server/provider failures.

## Security boundary

The ZIP upload is only an input transport. It does not authorize code execution, network access, patch application, persistent storage, or GitHub access. All repository data remains temporary and session-scoped as required by [SPEC.md](../SPEC.md).
