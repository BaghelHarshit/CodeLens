# CodeLens V1 API Contract

This document defines the implemented local-repository, Q&A, and code-review API contract. It is the frontend/backend contract for the current V1 implementation.

## Provider configuration

The API is provider-neutral. The default `fake` embedding and LLM providers support credential-free local checks. Live requests use Google Gemini when `CODELENS_EMBEDDING_PROVIDER=gemini` and/or `CODELENS_LLM_PROVIDER=gemini`, with `GEMINI_API_KEY` and the corresponding model settings configured in `.env`. Provider failures are returned through stable safe errors; keys, prompts, source dumps, and raw provider responses are never exposed.

## Repository input

V1 accepts a repository as a ZIP or RAR archive uploaded from the user's local machine. The browser must not send an arbitrary server filesystem path. A client submits the archive as `multipart/form-data`:

```http
POST /api/session/{session_id}/repository
Content-Type: multipart/form-data

repository=<repository.zip|repository.rar>
```

The upload field is named `repository`. The filename is informational only and must not determine the destination path. Accepted files have `.zip` or `.rar` extensions and common ZIP/RAR content types; the server validates the archive contents rather than trusting the filename or content type. RAR extraction requires the Python `rarfile` package and an installed `unrar`/`unrar-free` executable on the backend host.

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

The server treats every archive as untrusted data. The implemented upload endpoint validates the complete archive in a session-local staging directory and replaces `repo/` only after validation and extraction succeed; failures remove staging data and leave no partial repository available.

The accepted upload response is `202 Accepted` with `status: "indexing"`, accepted/skipped file counts, extracted bytes, and safe relative-path warnings. This ticket only hands off an accepted repository to the future indexing pipeline; it does not parse source files or make the session ready.

The server treats every archive as untrusted data:

- Reject an invalid or corrupt ZIP/RAR, an empty archive, and an archive containing no usable files.
- Reject password-protected RAR archives and report a safe error when the backend `unrar` tool is unavailable.
- Normalize member names to relative POSIX paths before writing them.
- Reject absolute paths, `..` traversal, NUL bytes, path collisions, and paths that resolve outside the session's repository directory.
- Reject symbolic links and unsupported special entries; only regular files and directories are accepted.
- Enforce compressed, extracted-byte, file-count, individual-file, and path-length limits while extracting.
- Do not follow links, run scripts/hooks/builds, import modules, or otherwise execute repository content.
- Do not expose server absolute paths in responses or logs.

A failed validation must leave no partially accepted repository available for indexing. The implementation should clean up any temporary extraction area before returning the error.

## Source-file discovery

After ingestion, discovery walks only the session repository and returns a deterministic, repository-relative inventory for parsing. Supported extensions currently map to Python (`.py`), JavaScript (`.js`, `.jsx`), TypeScript (`.ts`, `.tsx`), Java, Go, Rust, C/C++, C#, Ruby, PHP, Swift, and Kotlin. Files are ordered by normalized relative path.

Discovery skips ignored/generated/vendor directories, symlinks, unsupported extensions, empty files, binary or non-UTF-8 files, unreadable files, and files exceeding `CODELENS_MAX_FILE_BYTES`. It also enforces configured discovered-file and total-byte limits. Results report indexed files/bytes plus deterministic skip-reason counts; only relative paths and language labels are exposed. Discovery never imports or executes repository content and hands its inventory to the Tree-sitter parser.

## Tree-sitter parsing

The parser consumes the discovery inventory and returns symbol records containing `relative_path`, `symbol_name`, `symbol_type`, `language`, `source`, and 1-based inclusive `start_line`/`end_line` fields. It emits nested classes, functions, methods, and supported declaration types; files with no meaningful declarations receive a file-level fallback symbol. Empty, unreadable, unavailable-grammar, path-boundary, and syntax problems are returned as per-file diagnostics. Syntax errors do not abort other files or prevent valid symbols around the error from being returned. Diagnostics and symbols are deterministic and never expose absolute server paths.

## Code chunks and metadata

Chunking turns parsed symbols into bounded records for future embeddings. Each chunk contains `chunk_id`, relative source metadata, source text, 1-based inclusive chunk lines, parent symbol lines, and zero-based `fragment_index`/`fragment_count`. Symbols within the configured limit remain intact; oversized symbols are split deterministically by source lines with bounded overlap. IDs use the versioned `chunk-v1` SHA-256 scheme over relative path, language, symbol identity, parent lines, and fragment index, so identical input produces identical IDs independent of session paths. JSON serialization validates relative paths, non-empty source, and consistent line/fragment metadata; absolute paths and traversal segments are rejected. Parser diagnostics are retained alongside chunks for partial-failure reporting.

## Repository filtering

Ingestion preserves source files for indexing but does not promise that every archive member becomes an embedding. The later discovery stage ignores `.git/` and common generated/dependency/cache/vendor directories (for example `node_modules/`, `.venv/`, `dist/`, `build/`, `coverage/`, and `__pycache__/`). It also skips binary, oversized, and unsupported file types. Skips are reported as warnings/counts and do not fail an otherwise valid repository.

## Session and indexing states

A session is created independently through `POST /api/session`. The session manager creates an unpredictable ID and an isolated temporary workspace containing `repo/`, `index/`, and `metadata/`. These directories are server-owned and are never returned to clients as absolute paths. `DELETE /api/session/{session_id}` removes the workspace; repeating deletion is safe for the same in-memory session.

Repository/indexing state uses these values:

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

## Repository Q&A

Once a session is ready, clients may ask a bounded repository question:

```http
POST /api/session/{session_id}/chat
Content-Type: application/json

{"question":"Where is authentication handled?"}
```

A successful response contains an answer, safe repository-relative references, and an `insufficient_context` boolean. Questions are answered using only bounded context retrieved from the session's shared index; the entire repository is never sent by default. The question is trimmed and must contain 1–4,000 characters. Blank, oversized, not-ready, deleted, missing-session, and provider-failure requests return the documented JSON error shape.

Example request:

```bash
curl -X POST http://localhost:8000/api/session/<session-id>/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"Where is authentication handled?"}'
```

Grounded response:

```json
{
  "answer": "Authentication is handled by ...",
  "references": [
    {
      "chunk_id": "chunk-v1-example",
      "relative_path": "src/auth.py",
      "symbol_name": "authenticate",
      "symbol_type": "function",
      "language": "python",
      "start_line": 10,
      "end_line": 18,
      "score": 0.92
    }
  ],
  "insufficient_context": false
}
```

When no indexed chunk is relevant, the API returns HTTP `200` with `insufficient_context: true`, an explanatory answer, and an empty `references` array. The answer must not be treated as evidence beyond the listed repository-relative references.

Q&A errors use the common shape `{ "error": { "code": "...", "message": "..." } }`:

| HTTP | Code | Meaning |
| ---: | --- | --- |
| 404 | `SESSION_NOT_FOUND` | The session ID does not exist. |
| 409 | `SESSION_NOT_READY` | Indexing has not produced a ready shared index. |
| 410 | `SESSION_DELETED` | The session was explicitly deleted. |
| 422 | `INVALID_QUESTION` | The question is blank, malformed, or outside the 4,000-character bound. |
| 502 | `LLM_FAILED` | The configured language-model provider failed, refused, or returned unusable output. |

Insufficient-context example:

```json
{
  "answer": "There is insufficient repository context to answer this question.",
  "references": [],
  "insufficient_context": true
}
```

## Code review contract

Code review accepts either a manually supplied bounded unified diff or the latest commit from the uploaded local Git repository. The legacy `{\"diff\": \"...\"}` form remains manual review; clients may also send an explicit source:

```json
{"source":"manual","diff":"diff --git a/src/app.py b/src/app.py\\n--- a/src/app.py\\n+++ b/src/app.py\\n@@ -1 +1 @@\\n-old()\\n+new()\\n"}
```

Latest-commit review sends:

```json
{"source":"last_commit"}
```

The repository must contain usable Git metadata and a readable `HEAD`. Root commits are supported. A commit with no patch is rejected as `EMPTY_LAST_COMMIT`; repositories without metadata, unavailable commits, malformed Git output, command failures, and oversized patches produce stable safe Git errors without server paths, stderr, or raw output. Git access is read-only and never applies patches or executes repository content.

Ticket 017 selects a bounded unified diff as the normalized review input. Both sources are normalized into that same input and use the same retrieval index and workflow. The endpoint accepts JSON with the following forms:

```json
{"diff":"diff --git a/src/app.py b/src/app.py\\n--- a/src/app.py\\n+++ b/src/app.py\\n@@ -1 +1 @@\\n-old()\\n+new()\\n"}
```

```json
{"diff":"diff --git a/src/app.py b/src/app.py\\n--- a/src/app.py\\n+++ b/src/app.py\\n@@ -1 +1 @@\\n-old()\\n+new()\\n"}
```

Diffs are limited to 200,000 characters, 100 files, 500 hunks, and 10,000 parsed lines. Paths are normalized to repository-relative POSIX paths; absolute paths, traversal, NUL bytes, malformed headers/hunks, inconsistent hunk counts, blank input, and unsupported unstructured input are rejected. Parsing never reads or writes the repository, executes code, applies patches, or contacts a provider.

The normalized review input is versioned as `review-v1`. Each finding uses this shape:

```json
{
  "severity": "high",
  "file": "src/app.py",
  "line": 12,
  "issue": "The changed branch skips validation.",
  "explanation": "...",
  "suggested_fix": "Validate the value before returning it.",
  "category": "correctness",
  "confidence": 0.9
}
```

`severity` is one of `critical`, `high`, `medium`, `low`, or `info`; `file` is repository-relative; `line` is a positive 1-based line in the new file; and `issue`/`explanation` are required. `suggested_fix`, `category`, and `confidence` are optional, with confidence bounded from 0 to 1. Terminal review outcomes are `findings`, `no_findings`, and `insufficient_context`. Validation errors use `MISSING_DIFF`, `EMPTY_DIFF`, `DIFF_TOO_LARGE`, `MALFORMED_DIFF`, `UNSAFE_DIFF_PATH`, or `DIFF_LIMIT_EXCEEDED` and the common error shape.

Example future request:

```bash
curl -X POST http://localhost:8000/api/session/<session-id>/review \
  -H "Content-Type: application/json" \
  -d @review-request.json
```

### Review context preparation

Before the future review workflow invokes an LLM, Ticket 018 normalizes the parsed `review-v1` diff into bounded changed-file evidence and retrieves related repository chunks through the same session FAISS index and retrieval service used by Q&A. Each changed file retains hunk ranges, changed line kinds, and new-file line numbers; retrieval references retain repository-relative paths, symbols, languages, and line ranges.

Context preparation builds bounded queries from changed paths, hunk ranges, additions, and a related-tests hint. Queries, references, source sections, and total context are deduplicated and size-limited. Changed diff evidence is retained even when retrieval returns no matching chunks, which produces an `insufficient_context` signal for the later workflow. This stage never reads or executes repository code, invokes an LLM, applies patches, or creates a second index. It only consumes the normalized diff and the existing session-scoped index.

### Structured review workflow

Ticket 019 adds one bounded LangGraph workflow after diff normalization and shared-context retrieval. Its states validate the unified diff, retrieve context from the session's existing FAISS index, return `insufficient_context` without invoking the LLM when no indexed references are available, invoke the provider with bounded changed/retrieved evidence, and validate/normalize structured output. The graph is not a multi-agent system and never executes repository code or applies patches.

The provider response must be JSON containing a `findings` array (an empty array produces `no_findings`). Findings must use the Ticket 017 schema and be grounded in a changed repository-relative file and a positive new-file line represented by an addition in the diff. Invalid JSON, invalid findings, ungrounded findings, refusals, and provider failures produce a safe workflow error rather than exposing raw provider output, prompts, source dumps, or secrets. Prompt and response size limits are enforced before and after generation.

## Review endpoint

`POST /api/session/{session_id}/review` accepts a manual diff or `{\"source\":\"last_commit\"}`:

```json
{"diff":"diff --git a/src/app.py b/src/app.py\\n--- a/src/app.py\\n+++ b/src/app.py\\n@@ -1 +1 @@\\n-old()\\n+new()\\n"}
```

A successful response uses the workflow result contract:

```json
{"outcome":"findings","findings":[{"severity":"high","file":"src/app.py","line":12,"issue":"...","explanation":"...","suggested_fix":"..."}]}
```

`no_findings` returns an empty findings array. `insufficient_context` returns without invoking the LLM when the shared session index has no related references. Review errors use `{ "error": { "code": "...", "message": "..." } }`: `SESSION_NOT_FOUND` (404), `SESSION_DELETED` (410), `SESSION_NOT_READY` (409), `INVALID_DIFF` (422), `GIT_METADATA_MISSING`, `GIT_REPOSITORY_UNAVAILABLE`, `GIT_COMMIT_UNAVAILABLE`, `EMPTY_LAST_COMMIT`, `MALFORMED_LAST_COMMIT`, or `GIT_DIFF_TOO_LARGE` (422), `GIT_COMMAND_FAILED` (502), `MALFORMED_LLM_OUTPUT` or `LLM_FAILED` (502), and `REVIEW_FAILED` (500). The endpoint never executes repository code, applies patches, creates a second index, or exposes provider prompts/raw responses.

```bash
curl -X POST http://localhost:8000/api/session/<session-id>/review \\
  -H "Content-Type: application/json" \\
  -d @review-request.json
```

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
| `UNSUPPORTED_ARCHIVE` | The upload is not a supported ZIP or RAR input. |
| `UPLOAD_TOO_LARGE` | The compressed upload exceeds its limit. |
| `INVALID_ARCHIVE` | The archive is corrupt, empty, encrypted, or unsafe. |
| `RAR_TOOL_UNAVAILABLE` | RAR extraction requires an unavailable backend `unrar` tool. |
| `EXTRACTION_LIMIT_EXCEEDED` | Extracted bytes, files, path length, or nesting exceed a limit. |
| `EMPTY_REPOSITORY` | No usable repository files remain after validation/filtering. |
| `INDEXING_FAILED` | A fatal indexing/provider failure occurred. |

HTTP status codes should be conventional: `400` for malformed input, `404` for an unknown session, `409` for an invalid lifecycle state, `413` for size limits, and `500`/`503` for server/provider failures.

## Security boundary

The ZIP upload is only an input transport. It does not authorize code execution, network access, patch application, persistent storage, or GitHub access. All repository data remains temporary and session-scoped as required by [SPEC.md](../SPEC.md).
