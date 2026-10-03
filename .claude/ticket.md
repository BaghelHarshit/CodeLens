# CodeLens V1 Ticket System

Source of truth: [SPEC.md](../SPEC.md)

Statuses: `TODO`, `IN PROGRESS`, `BLOCKED`, `DONE`. Complete tickets in dependency order. Every ticket requires implementation, tests (or a documented manual check), error handling, and relevant documentation.

## Definition of done

Deliver a local-repository, session-based CodeLens V1 using React + TypeScript + Vite, FastAPI + Python, Tree-sitter, OpenAI embeddings/LLM, FAISS, and one shared RAG index for Q&A and code review. V1 excludes databases, persistent storage, GitHub ingestion, microservices, Redis, arbitrary code execution, and automatic patch application.

---

## Phase 0 — Foundation

### TICKET-001 — Git project setup and baseline
- **Status:** DONE | **Priority:** P0 | **Depends on:** None
- Initialize Git and the initial branch.
- Add `.gitignore` for Python, Node, build output, IDE files, environment files, temporary sessions, FAISS artifacts, and logs.
- Add a safe `.env.example` containing names only; never commit secrets.
- Add `README.md` with setup, architecture, commands, and links to `SPEC.md` and this file.
- Create `backend/`, `frontend/`, and `tests/` directories.
- **Done when:** the baseline commit is clean, reproducible, and contains no secrets or generated artifacts.

### TICKET-002 — Define local repository input contract
- **Status:** DONE | **Priority:** P0 | **Depends on:** 001
- Choose and document the simplest upload/directory transport.
- Define archive types, size limits, path normalization, ignored paths, invalid-input behavior, and indexing states.
- **Done when:** frontend and backend share one secure, documented contract.

### TICKET-003 — Scaffold backend and frontend
- **Status:** DONE | **Priority:** P0 | **Depends on:** 001, 002
- Configure Python dependencies: FastAPI, Uvicorn, Tree-sitter, FAISS, OpenAI/LangChain, validation, and tests.
- Scaffold React + TypeScript + Vite and scripts.
- Add configuration loading, environment validation, CORS, health endpoint, and minimal UI shell.
- **Done when:** both apps install and run with documented commands.

### TICKET-004 — Establish quality gates
- **Status:** DONE | **Priority:** P0 | **Depends on:** 003
- Configure backend tests, formatting, linting, and type checks; configure frontend tests, linting, and type checks.
- Add a safe fixture repository, offline fake providers, and CI if appropriate.
- **Done when:** one command runs checks without OpenAI credentials.

## Phase 1 — Sessions and indexing

### TICKET-005 — Temporary session manager
- **Status:** DONE | **Priority:** P0 | **Depends on:** 003, 004
- Implement secure random IDs, lookup, state transitions, and deletion.
- Create isolated `repo/`, `index/`, and `metadata/` workspaces.
- Make cleanup safe and idempotent; never delete outside a session root.
- **Done when:** session creation, isolation, lifecycle errors, and cleanup are tested.

### TICKET-006 — Secure repository ingestion
- **Status:** DONE | **Priority:** P0 | **Depends on:** 002, 005
- Implement `POST /api/session/{session_id}/repository`.
- Validate type, size, empty input, traversal, symlinks, collisions, and outside writes.
- Exclude configured generated/vendor paths as appropriate; never execute repository code.
- **Done when:** valid fixtures work and malicious/invalid input fails safely.

### TICKET-007 — Source-file discovery
- **Status:** DONE | **Priority:** P0 | **Depends on:** 006
- Map supported extensions to languages/grammars; skip binaries, oversized, generated, vendor, and unsupported files.
- Record counts, limits, and skip reasons.
- **Done when:** discovery is deterministic, bounded, and tested.

### TICKET-008 — Tree-sitter parser
- **Status:** DONE | **Priority:** P0 | **Depends on:** 007
- Extract files, classes, functions, methods, and relevant declarations.
- Capture source, relative path, symbol name/type, language, start line, and end line.
- Continue after malformed files and record diagnostics.
- **Done when:** nested symbols, multiple languages, empty files, and syntax errors are covered.

### TICKET-009 — Code chunking and metadata
- **Status:** DONE | **Priority:** P0 | **Depends on:** 008
- Use meaningful symbols as primary chunks and file/fallback chunks where needed.
- Bound oversized-symbol splitting while retaining parent metadata.
- Define stable IDs and safe serialization; never expose absolute server paths.
- **Done when:** metadata round-trips and every chunk maps to source lines.

### TICKET-010 — Embedding provider abstraction
- **Status:** DONE | **Priority:** P0 | **Depends on:** 009
- Configure the Google Gemini API key, embedding model, batch, timeout, and retry through environment variables. The project will use the user's free Google Gemini API key for live embeddings instead of an OpenAI key. Gemini provides a compatible embedding API/model, subject to the account's current free-tier quota and model availability.
- Define a provider interface so Gemini is replaceable by another embedding provider later through configuration and a small adapter change, without changing chunking, retrieval, or indexing workflows.
- Batch calls, retry bounded transient failures, and provide deterministic fake embeddings.
- Do not log source or keys.
- **Done when:** production Gemini and offline providers are interchangeable.

### TICKET-011 — FAISS index and metadata store
- **Status:** DONE | **Priority:** P0 | **Depends on:** 009, 010
- Build one FAISS index per session and persist/reload only within its workspace.
- Validate dimensions, empty indexes, top-k search, stable ordering, and metadata mapping.
- **Done when:** fixture search returns file/symbol/line metadata and deletion removes artifacts.

### TICKET-012 — Indexing orchestration and status API
- **Status:** DONE | **Priority:** P0 | **Depends on:** 005–011
- Connect ingestion → discovery → parsing → chunking → embeddings → FAISS.
- Add progress/status, summary counts, retries, readiness gates, and partial-failure reporting.
- **Done when:** sessions predictably become ready or failed, with integration tests.

## Phase 2 — Shared RAG and repository Q&A

### TICKET-013 — Shared retrieval service
- **Status:** DONE | **Priority:** P0 | **Depends on:** 011, 012
- Embed user/review queries, retrieve top-k from the session index, bound context, deduplicate results, and format safe references.
- Prove Q&A and review use the same retriever/index.
- **Done when:** retrieval is bounded, metadata-rich, session-scoped, and tested.

### TICKET-014 — Shared Gemini LLM client
- **Status:** DONE | **Priority:** P0 | **Depends on:** 003
- Centralize the Google Gemini model, temperature, token, timeout, retry, and error handling. The project will use the user's free Google Gemini API key for live chat and code-review LLM requests.
- Keep the provider boundary independent of Gemini so the embedding and LLM providers can be changed later with minimal adapter/configuration changes.
- Define a provider interface and configuration boundary so the Gemini LLM can be replaced with another provider later through a small adapter/configuration change, without changing Q&A or code-review workflows.
- Add a fake LLM; validate malformed/refusal responses; redact secrets and avoid full-context logs.
- **Done when:** both workflows use one Gemini client and offline tests never call the Gemini API.

### TICKET-015 — Repository Q&A RAG workflow
- **Status:** DONE | **Priority:** P0 | **Depends on:** 013, 014
- Use the shared, provider-agnostic LLM client and the configured free Google Gemini API key for live responses; offline tests must use the fake LLM. Keep provider selection replaceable without changing the RAG workflow.
- Implement `POST /api/session/{session_id}/chat` with validation.
- Retrieve relevant code, build a code-aware prompt, call the LLM, and return grounded answer plus references.
- Represent insufficient context clearly; do not send the whole repository by default.
- **Done when:** fixture questions return grounded answers/references and not-ready sessions are rejected.

### TICKET-016 — Q&A contract and end-to-end tests
- **Status:** DONE | **Priority:** P0 | **Depends on:** 015
- Stabilize API models and document curl examples.
- Test fake providers, empty retrieval, long questions, provider failures, and deleted sessions.
- **Done when:** happy and failure paths pass automatically.

## Phase 3 — RAG code review

### TICKET-017 — Define diff input and finding schema
- **Status:** DONE | **Priority:** P0 | **Depends on:** 002, 013
- Choose unified diff or selected changed-code input as the LangGraph review workflow input.
- Validate missing, empty, malformed, and oversized changes.
- Define severity, file, line, issue, explanation, suggested fix, and optional category/confidence.
- **Done when:** versionable request/response contracts are documented and suitable for graph-state validation.

### TICKET-018 — Retrieve review context
- **Status:** TODO | **Priority:** P0 | **Depends on:** 013, 017
- Parse/normalize changed files and hunks without execution.
- Build bounded queries from changed symbols/files and relevant tests.
- Retrieve surrounding/related code from the same FAISS index as Q&A.
- Produce the bounded context and metadata consumed by the LangGraph review workflow.
- **Done when:** context includes changed code and relevant existing code where available.

### TICKET-019 — Structured code-review workflow
- **Status:** TODO | **Priority:** P0 | **Depends on:** 014, 018
- Implement the code-review workflow with LangGraph as a single bounded state graph, not a multi-agent system.
- Define graph states/nodes for input validation, context sufficiency, shared retrieval, Gemini LLM invocation, structured finding validation/normalization, and safe terminal outcomes.
- Use the shared Gemini LLM client and the configured free Google Gemini API key for live review analysis; offline tests must use the fake LLM.
- Prompt for structured, evidence-based findings grounded in changed code and retrieved repository context.
- Safely handle malformed/refusal/provider results, retry only within bounded limits, include references and no-issue/insufficient-context outcomes, and never apply patches.
- Reuse the shared retrieval service, session-scoped FAISS index, and provider boundary; do not create a separate review index or agent architecture.
- **Done when:** the LangGraph workflow produces schema-valid, grounded findings and tested transitions for success, no-findings, insufficient-context, malformed-output, and provider-failure paths.

### TICKET-020 — Review API and tests
- **Status:** TODO | **Priority:** P0 | **Depends on:** 019
- Implement `POST /api/session/{session_id}/review` over the LangGraph workflow.
- Test graph transitions and API behavior for valid, empty, malformed, missing-file, no-finding, insufficient-context, malformed-LLM, refusal, and provider-failure cases.
- Verify the API and graph use the same session FAISS index/retriever as Q&A and never apply patches.
- **Done when:** API, LangGraph state transitions, shared-index behavior, and error contracts are documented and automated.

## Phase 4 — React UI

### TICKET-021 — Session and repository UI
- **Status:** TODO | **Priority:** P0 | **Depends on:** 012, 016
- Add session creation, repository input, upload, polling, progress, warnings, errors, retry, and end-session controls.
- Never display raw server paths.
- **Done when:** a user can reach ready or recover from failure without developer tools.

### TICKET-022 — Q&A UI
- **Status:** TODO | **Priority:** P0 | **Depends on:** 016, 021
- Add question input, loading/error states, answer display, and file/symbol/line references.
- Disable or explain Q&A before readiness.
- **Done when:** multiple questions and supporting references work in one session.

### TICKET-023 — Code-review UI
- **Status:** TODO | **Priority:** P0 | **Depends on:** 020, 021
- Add diff input/validation and findings grouped by severity with file/line, explanation, suggested fix, and context.
- Label AI suggestions and state that code is not automatically modified.
- **Done when:** findings, no-findings, loading, and failure states are understandable.

### TICKET-024 — Accessibility and frontend resilience
- **Status:** TODO | **Priority:** P1 | **Depends on:** 022, 023
- Add semantic markup, labels, keyboard navigation, focus states, contrast, responsive layout, timeout/network/session-expiry handling, and component tests.
- **Done when:** critical flows are keyboard-usable and tested.

## Phase 5 — Hardening and release

### TICKET-025 — Security and resource-limit review
- **Status:** TODO | **Priority:** P0 | **Depends on:** 006, 012, 020, 024
- Test traversal, symlinks, oversized inputs/files, malformed encodings, prompt injection in source comments, isolation, and abandoned sessions.
- Confirm no code execution, secret leakage, or unsafe logging; add request/file/chunk/context/time/concurrency limits.
- **Done when:** security checklist and mitigations/tests are documented.

### TICKET-026 — Observability and diagnostics
- **Status:** TODO | **Priority:** P1 | **Depends on:** 012, 016, 020
- Add safe structured logs, correlation IDs, stage durations/counts, health/readiness, and stable error codes.
- **Done when:** failures are diagnosable without keys, full source, prompts, or responses in logs.

### TICKET-027 — Full integration and smoke tests
- **Status:** TODO | **Priority:** P0 | **Depends on:** 025, 026
- Test create → ingest → index → Q&A → review → delete with fake providers.
- Verify contracts, CORS, references, shared index, cleanup, and all SPEC success criteria.
- **Done when:** all critical checks pass or have a documented manual check.

### TICKET-028 — Final documentation and demo
- **Status:** TODO | **Priority:** P0 | **Depends on:** 027
- Document prerequisites, setup, environment, commands, architecture, API examples, limits, supported languages, temporary data, safety, and limitations.
- Add a fixture-based demo checklist.
- **Done when:** a new developer can run and demo the complete workflow from README.

### TICKET-029 — V1 release
- **Status:** TODO | **Priority:** P0 | **Depends on:** 028
- Run all gates, check history and secrets, tag a reproducible V1 release, and record deferred work.
- **Done when:** the release is tested, documented, and aligned with SPEC.md.

## Deferred final phase — GitHub integration

### TICKET-030 — GitHub repository retrieval
- **Status:** DEFERRED — do not start before TICKET-029
- **Priority:** P2 | **Depends on:** 029
- Add optional GitHub URL input through the GitHub API with authentication, URL validation, permissions, rate limits, and size limits.
- Reuse the existing session, ingestion, parser, embeddings, FAISS, Q&A, and review pipeline; do not create a parallel architecture.
- For a changed GitHub revision, compare the current and previous indexed revisions where available; reuse unchanged embeddings, replace embeddings for added or modified chunks, and remove embeddings for deleted chunks. The repository source does not need permanent storage.
- Keep fetched source and embeddings temporary for the active analysis unless a later persistence design explicitly requires retaining embeddings and revision/chunk metadata. Do not require durable snapshots or embeddings for the initial GitHub workflow.
- **Done when:** GitHub is optional, local behavior is unchanged, and the feature does not expand V1 scope.

## Recommended execution order

1. 001–004: Git, scaffolding, and quality gates.
2. 005–012: session/indexing milestone.
3. 013–016: first useful demo — local fixture → index → Q&A.
4. 017–020: code-review milestone, including the bounded LangGraph workflow.
5. 021–024: usable UI.
6. 025–029: hardening and V1 release.
7. 030: GitHub only after V1 is complete.

Parallelize only after dependencies are complete. Keep SPEC.md authoritative when this list and implementation differ; document deliberate architectural changes.
