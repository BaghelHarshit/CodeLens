# CodeLens

CodeLens is an AI-powered repository intelligence and code-review tool. It accepts a local code repository, indexes meaningful source-code units, and uses retrieval-augmented generation (RAG) to answer repository questions and review local changes.

This repository is a fresher-level SDE/AI placement project. The product scope is defined in [SPEC.md](SPEC.md), the API is specified in [docs/api-contract.md](docs/api-contract.md), and implementation work is tracked in [.claude/ticket.md](.claude/ticket.md).

## V1 scope

The implemented V1 stack is:

- **Frontend:** React, TypeScript, and Vite
- **Backend:** Python and FastAPI
- **Code parsing:** Tree-sitter
- **Embeddings:** Google Gemini API (with a deterministic offline fake provider)
- **LLM:** provider-neutral adapter with Google Gemini as the live provider and a deterministic fake provider for offline checks
- **Vector store:** temporary FAISS index
- **RAG/workflow:** LangChain and LangGraph where useful
- **Storage:** temporary, session-scoped server filesystem
- **API:** REST

The backend will index a local repository once per temporary session. Q&A and code review use the same shared, bounded retrieval service and repository index, returning source metadata such as repository-relative file paths, symbols, and line ranges. Retrieval limits context size and deduplicates chunks before the provider-neutral LLM workflow consumes it. Gemini is the configured live LLM adapter; offline tests use the fake adapter and never call Gemini.

## Ticket progress

- TICKET-001 — Git project setup and baseline: **DONE**
- TICKET-002 — Local repository input contract: **DONE**
- TICKET-003 — Backend and frontend scaffold: **DONE**
- TICKET-004 through TICKET-024, CL-001, and CL-002 — **DONE**
- TICKET-024A onward — planned hardening and release work

V1 deliberately does **not** include GitHub retrieval, a database, persistent user accounts/history, microservices, Redis, Kubernetes, autonomous code modification, automatic patch application, or execution of repository code. GitHub retrieval is deferred until after the V1 release.

## Current status

The implemented V1 workflow creates an isolated temporary session, safely ingests ZIP/RAR repositories, discovers and indexes source code, and exposes shared-index Q&A and code review. Review accepts either a manual unified diff or the latest commit from uploaded Git metadata.

## Run locally

### Backend

From the repository root, create and activate a Python 3.11+ virtual environment, then install the backend dependencies:

```bash
python -m venv .venv
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r backend/requirements.txt
uvicorn app.main:app --app-dir backend --reload
```

The API is available at `http://127.0.0.1:8000`; check `GET /health` or `GET /api/health`.

### Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL (normally `http://localhost:5173`). Set `VITE_API_BASE_URL` in `.env` when the API is hosted elsewhere. Backend settings are loaded from the root `.env` file using the names in [.env.example](.env.example). Gemini credentials are not needed for the quality suite or offline local checks; use the fake providers by default. Live Gemini operation requires `GEMINI_API_KEY`. RAR uploads additionally require `rarfile` and an installed `unrar`/`unrar-free` executable.

### Quality gates

Run the complete credential-free quality suite from the repository root:

```bash
python scripts/check.py
```

The command runs backend tests, Ruff formatting and lint checks, mypy, frontend typechecking, the production build, ESLint, and Vitest. It uses only the safe fixture repository and offline provider fakes; no `.env`, Gemini key, network provider, or generated session data is required.

Individual checks can be run while diagnosing failures:

```bash
pytest -c backend/pyproject.toml backend/tests
ruff format --check backend/app backend/tests
ruff check backend/app backend/tests
mypy backend/app
cd frontend && npm run typecheck && npm run build && npm run lint && npm test
```

These gates run in CI through [`.github/workflows/quality.yml`](.github/workflows/quality.yml).

### Safe test fixture

[`tests/fixtures/sample-repository/`](tests/fixtures/sample-repository/) is an inert repository fixture for indexing tests. It contains small Python and TypeScript source files, no secrets, and no executable hooks or generated artifacts.

The frontend lint and test scripts are included for ticket-level quality gates; future tickets should preserve the credential-free test boundary.

## Repository layout

```text
.
├── backend/       # FastAPI application
├── frontend/      # React/Vite application
├── tests/         # Shared and integration tests
├── docs/          # Shared API and implementation contracts
├── SPEC.md        # Product and architecture specification
└── .claude/
    └── ticket.md  # Ordered implementation tickets
```

## Initial setup

For a fresh checkout, install the documented dependencies, copy `.env.example` to `.env` when configuration is needed, and review the specification and API contract:

```text
SPEC.md
.claude/ticket.md
```

The environment template is [.env.example](.env.example). Copy it to `.env` only when local application configuration is needed. Do not commit `.env` or API keys.

### Local repository input

V1 uses browser-friendly ZIP or RAR uploads rather than accepting arbitrary server filesystem paths. RAR support requires the backend `rarfile` dependency and an installed `unrar`/`unrar-free` executable. The frontend will send a `repository` field using `multipart/form-data` to the session repository endpoint. Upload and extraction limits, safe archive rules, session states, and error codes are documented in [docs/api-contract.md](docs/api-contract.md). Once indexing is ready, ask a grounded repository question with `POST /api/session/{session_id}/chat` and JSON such as `{\"question\":\"Where is authentication handled?\"}`. The response includes an answer, safe file/symbol/line references, and an `insufficient_context` flag.

### Browser Q&A

After repository indexing reaches `Ready`, the session page enables the **Ask about your repository** form. Each question is sent to the session-scoped `/chat` endpoint and the answer is grounded in retrieved repository context. Responses show supporting relative file paths, symbols, and line ranges when available; an insufficient-context response is presented explicitly. Questions and answers remain in the active browser session and are cleared when the session ends or is retried.

### Browser code review

When indexing reaches `Ready`, the **Review code changes** panel can accept a manual unified diff up to 200,000 characters or review the latest commit from the uploaded repository. Latest-commit review requires usable Git metadata and a readable `HEAD`; it supports root commits and rejects empty commits clearly. Both sources use `POST /api/session/{session_id}/review`, the same parser, shared retrieval index, and workflow. Findings are grouped by critical, high, medium, low, or informational severity and include repository-relative file, new-file line, issue, explanation, and optional suggested fix, category, and confidence. The UI distinguishes no findings and insufficient context, reports provider errors safely, and states that suggestions are advisory: CodeLens never applies patches or modifies the repository automatically.

## Development principles

1. Prefer simple, explicit designs over unnecessary infrastructure.
2. Treat repository files as untrusted input and never execute them.
3. Keep sessions isolated and temporary.
4. Retrieve relevant code before sending context to the LLM; do not send the whole repository by default.
5. Preserve file, symbol, language, and line metadata through the indexing pipeline.
6. The implemented deviations from the original draft are deliberate: Gemini replaces OpenAI behind provider-neutral adapters, ZIP/RAR uploads are the local transport, and review supports both manual diffs and latest-commit Git sources.

## License

Licensing is currently **pending** and will be decided before public distribution.
