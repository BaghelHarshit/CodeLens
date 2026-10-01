# CodeLens

CodeLens is an AI-powered repository intelligence and code-review tool. It accepts a local code repository, indexes meaningful source-code units, and uses retrieval-augmented generation (RAG) to answer repository questions and review local changes.

This repository is currently being built as a fresher-level SDE/AI placement project. The product scope is defined in [SPEC.md](SPEC.md), and the implementation work is tracked in [.claude/ticket.md](.claude/ticket.md).

## V1 scope

The planned V1 stack is:

- **Frontend:** React, TypeScript, and Vite
- **Backend:** Python and FastAPI
- **Code parsing:** Tree-sitter
- **Embeddings and LLM:** OpenAI API
- **Vector store:** temporary FAISS index
- **RAG/workflow:** LangChain and LangGraph where useful
- **Storage:** temporary, session-scoped server filesystem
- **API:** REST

The backend will index a local repository once per temporary session. Q&A and code review will use the same repository index and return source metadata such as file paths, symbols, and line ranges.

V1 deliberately does **not** include GitHub retrieval, a database, persistent user accounts/history, microservices, Redis, Kubernetes, autonomous code modification, automatic patch application, or execution of repository code. GitHub retrieval is deferred until after the V1 release.

## Current status

The repository baseline is established by TICKET-001. Application scaffolding and runtime functionality are planned in the following tickets.

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
