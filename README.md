# CodeLens

CodeLens is an AI-powered repository intelligence and code-review tool. It accepts a local code repository, indexes meaningful source-code units, and uses retrieval-augmented generation (RAG) to answer repository questions and review local changes.

This repository is currently being built as a fresher-level SDE/AI placement project. The product scope is defined in [SPEC.md](SPEC.md), and the implementation work is tracked in [.claude/ticket.md](.claude/ticket.md).

## V1 scope

The planned V1 stack is:

- **Frontend:** React, TypeScript, and Vite
- **Backend:** Python and FastAPI
- **Code parsing:** Tree-sitter
- **Embeddings:** Google Gemini API (with a deterministic offline fake provider)
- **LLM:** provider adapter configured separately
- **Vector store:** temporary FAISS index
- **RAG/workflow:** LangChain and LangGraph where useful
- **Storage:** temporary, session-scoped server filesystem
- **API:** REST

The backend will index a local repository once per temporary session. Q&A and code review use the same shared, bounded retrieval service and repository index, returning source metadata such as repository-relative file paths, symbols, and line ranges. Retrieval limits context size and deduplicates chunks before a future LLM workflow consumes it.

## Ticket progress

- TICKET-001 — Git project setup and baseline: **DONE**
- TICKET-002 — Local repository input contract: **DONE**
- TICKET-003 — Backend and frontend scaffold: **DONE**
- TICKET-004 onward — planned

V1 deliberately does **not** include GitHub retrieval, a database, persistent user accounts/history, microservices, Redis, Kubernetes, autonomous code modification, automatic patch application, or execution of repository code. GitHub retrieval is deferred until after the V1 release.

## Current status

TICKET-003 scaffolds the FastAPI backend and React/Vite frontend. Repository ingestion and runtime workflows are planned in the following tickets.

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

Open the Vite URL (normally `http://localhost:5173`). Set `VITE_API_BASE_URL` in `.env` when the API is hosted elsewhere. Backend settings are loaded from the root `.env` file using the names in [.env.example](.env.example). OpenAI credentials are not needed for the scaffold health check or UI shell.

### Quality gates

Run the complete credential-free quality suite from the repository root:

```bash
python scripts/check.py
```

The command runs backend tests, Ruff formatting and lint checks, mypy, frontend typechecking, the production build, ESLint, and Vitest. It uses only the safe fixture repository and offline provider fakes; no `.env`, OpenAI key, network provider, or generated session data is required.

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
├── backend/       # FastAPI application (later ticket)
├── frontend/      # React/Vite application (later ticket)
├── tests/         # Shared and integration tests
├── docs/          # Shared API and implementation contracts
├── SPEC.md        # Product and architecture specification
└── .claude/
    └── ticket.md  # Ordered implementation tickets
```

## Initial setup

Prerequisites and exact dependency commands will be added with TICKET-003. For now, clone or open the repository and review the specification and ticket list:

```text
SPEC.md
.claude/ticket.md
```

The environment template is [.env.example](.env.example). Copy it to `.env` only when local application configuration is needed. Do not commit `.env` or API keys.

### Local repository input

V1 uses a browser-friendly ZIP upload rather than accepting arbitrary server filesystem paths. The frontend will send a `repository` field using `multipart/form-data` to the session repository endpoint. Upload and extraction limits, safe archive rules, session states, and error codes are documented in [docs/api-contract.md](docs/api-contract.md). Ingestion and indexing are implemented by later tickets.

## Development principles

1. Prefer simple, explicit designs over unnecessary infrastructure.
2. Treat repository files as untrusted input and never execute them.
3. Keep sessions isolated and temporary.
4. Retrieve relevant code before sending context to the LLM; do not send the whole repository by default.
5. Preserve file, symbol, language, and line metadata through the indexing pipeline.
6. Document deliberate deviations from [SPEC.md](SPEC.md).

## License

Licensing is currently **pending** and will be decided before public distribution.
