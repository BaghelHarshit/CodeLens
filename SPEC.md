# CodeLens --- Project Specification

## 1. Project Overview

**Project Name:** CodeLens --- AI-Powered Repository Intelligence & Code
Review

CodeLens is a lightweight AI-powered developer tool that allows a user
to provide a **local code repository** and then:

1.  Ask natural-language questions about the repository.
2.  Perform AI-powered code review using the repository's context.

The project is intentionally scoped for a **fresher-level SDE/AI
placement project**. The goal is a working, technically defensible
end-to-end system rather than a production-scale distributed platform.

The initial version is **local-repository based and session-based**.
GitHub repository retrieval will be added only as a final/deferred
phase.

------------------------------------------------------------------------

# 2. Core Goals

The V1 system must:

-   Accept a local repository from the user.
-   Parse the repository's source code.
-   Divide code into meaningful units such as functions, classes,
    methods, and relevant file-level chunks.
-   Generate embeddings for the code chunks.
-   Store the embeddings in a temporary vector store.
-   Use RAG for repository Q&A.
-   Use the same RAG infrastructure for AI-powered code review.
-   Provide useful source metadata with retrieved context, such as file
    path, symbol name, and line numbers.
-   Keep all repository/session data temporary.
-   Avoid unnecessary infrastructure and over-engineering.

------------------------------------------------------------------------

# 3. Explicit Scope Decisions

These decisions are part of the project definition and should be treated
as constraints unless explicitly changed later.

## 3.1 Input

### V1

The user provides a **local repository**.

The system does NOT retrieve or clone repositories from GitHub in V1.

Possible local input mechanisms may include:

-   Local repository path, or
-   Uploading/providing a repository directory through the application.

The implementation should choose the simplest practical mechanism for
local repository ingestion.

### Deferred

GitHub repository retrieval using the GitHub API is explicitly deferred
to the **last phase of the project**.

Do not build GitHub repository ingestion during the initial
implementation.

------------------------------------------------------------------------

## 3.2 Repository Storage

CodeLens does not need to permanently store the repository source. The
user asks questions about the current state of the repository and works
with that uploaded or fetched state during the active analysis session.

For a local repository upload, repository files are stored temporarily on
the server filesystem for the duration of the session. The local upload is
assumed to be the repository state the user wants to understand; the user
does not repeatedly upload it as the repository changes during that
session.

Conceptually:

``` text
/tmp/codelens/
    <session_id>/
        repo/       # temporary local upload or GitHub checkout
        index/      # temporary FAISS index
        metadata/   # temporary chunk metadata
```

The local repository source is not permanently stored. When the session
ends or is explicitly deleted, the temporary repository, index, and
metadata should be cleaned up.

GitHub retrieval is a deferred feature. For that feature, CodeLens does
not need to retain the repository source permanently. The fetched
repository and its embeddings may remain temporary for the active analysis
session. When a newer GitHub revision is processed, compare it with the
previous indexed revision when available, reuse embeddings for unchanged
chunks, replace embeddings for added or modified chunks, and remove
embeddings for deleted chunks. Store the resulting embedding set for the
current analysis/revision. Durable embeddings across sessions are optional
future behavior, not a requirement of the GitHub URL feature. This applies
only to the deferred GitHub URL workflow, not to the local-upload V1
workflow.

The local-upload workflow does not need repository refresh handling: the
user uploads the repository state they want to understand and work with,
and does not repeatedly upload it during that analysis session.

If a future implementation needs to compare GitHub revisions across
separate sessions, it may store only the embedding set and revision/chunk
metadata, subject to the future persistence and privacy design. The source
repository still does not need to be retained.

------------------------------------------------------------------------

## 3.3 Database

**No database is used in V1.**

Do NOT introduce:

-   PostgreSQL
-   pgvector
-   MongoDB
-   Redis
-   any persistent database

The project is intentionally stateless/session-based.

A database may be introduced in a future version to support:

-   Persistent repositories
-   User accounts
-   Chat history
-   Previous PR reviews
-   Optional embedding retention for deferred GitHub revision comparison
-   Incremental indexing for changed GitHub revisions

This is a future extension, not part of the current implementation.

------------------------------------------------------------------------

# 4. Technology Stack

## Frontend

-   React
-   TypeScript
-   Vite

The frontend is responsible for:

-   Repository input
-   Session interaction
-   Repository indexing status
-   Repository Q&A UI
-   Code review UI
-   Displaying answers and review findings
-   Displaying source/file/line references

------------------------------------------------------------------------

## Backend

-   Python
-   FastAPI

FastAPI is responsible for:

-   API endpoints
-   Session management
-   Local repository ingestion
-   Repository parsing
-   Embedding generation
-   Vector indexing
-   RAG retrieval
-   LLM interaction
-   Code review workflow

The initial architecture should use **one backend application**, not
microservices.

------------------------------------------------------------------------

## LLM

-   OpenAI API

The LLM is used for:

-   Repository question answering
-   Code explanation
-   Code review
-   Identifying potential issues
-   Providing review reasoning and suggestions

The LLM should NOT receive the entire repository by default.

Relevant repository context should first be retrieved using RAG.

------------------------------------------------------------------------

## Embeddings

Use an OpenAI embedding model for repository code chunks and user/review
queries.

The exact embedding model can be configured through environment
variables/configuration rather than hard-coded throughout the
application.

------------------------------------------------------------------------

## Vector Store

-   FAISS

FAISS is the temporary vector store for V1.

It is appropriate because:

-   The system is session-based.
-   Persistent storage is not required.
-   Repository embeddings only need to exist during the active analysis
    session.
-   It avoids introducing a database solely for vector storage.

The FAISS index and associated metadata are stored temporarily in the
session workspace.

------------------------------------------------------------------------

## Code Parsing

-   Tree-sitter

Tree-sitter should be used to understand the syntactic structure of
source code.

The system should prefer meaningful code units such as:

``` text
File
 ├── Class
 │    ├── Method
 │    └── Method
 ├── Function
 └── Other relevant declarations
```

The project should NOT rely exclusively on arbitrary fixed-size text
chunking.

------------------------------------------------------------------------

## RAG / LLM Framework

-   LangChain
-   LangGraph

Use these selectively.

### LangChain

Use for components such as:

-   Embeddings
-   LLM interaction
-   Retrieval abstractions
-   Prompt/context handling

### LangGraph

Use LangGraph explicitly for the structured code-review workflow, where
bounded state transitions and validation branches are useful. The graph
must remain a single, bounded workflow rather than a multi-agent system.
Its nodes should orchestrate existing services:

``` text
Validate diff
      ↓
Retrieve shared repository context
      ↓
Context sufficient?
  ├── no → insufficient-context outcome
  └── yes
          ↓
      Invoke shared LLM
          ↓
      Validate/normalize findings
  ├── malformed/refusal → bounded safe failure
  ├── no findings → no-issue outcome
  └── valid findings → grounded review outcome
```

The review graph must reuse the shared retrieval service, the session's
single FAISS index, and the provider-neutral LLM client. It must not create
separate vector stores, providers, persistence, agents, or execution
capabilities merely to support the graph. LangGraph may be used for Q&A
later if its state branching becomes useful, but Q&A does not require a
graph in the initial implementation.

------------------------------------------------------------------------

## API Communication

-   REST API

The frontend communicates with the FastAPI backend through REST
endpoints.

WebSockets are not required for V1.

Polling may be used for long-running indexing/review status if needed.

------------------------------------------------------------------------

# 5. High-Level Architecture

``` text
                         ┌───────────────────────┐
                         │      React + TS        │
                         │         Vite          │
                         └───────────┬───────────┘
                                     │
                                  REST API
                                     │
                                     ▼
                         ┌───────────────────────┐
                         │    FastAPI Backend    │
                         │        Python         │
                         └───────────┬───────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              │                      │                      │
              ▼                      ▼                      ▼
       Session Manager       Local Repository        RAG Pipeline
                                    │                      │
                                    ▼                      │
                            Temporary Filesystem           │
                                    │                      │
                                    ▼                      │
                               Tree-sitter                 │
                                    │                      │
                                    ▼                      │
                              Code Chunks                  │
                                    │                      │
                                    ▼                      │
                              Embeddings                   │
                                    │                      │
                                    ▼                      │
                                  FAISS ◄──────────────────┘
                                    │
                         ┌──────────┴──────────┐
                         │                     │
                         ▼                     ▼
                  Repository Q&A          Code Review
                         │                     │
                         └──────────┬──────────┘
                                    ▼
                              OpenAI LLM
                                    │
                                    ▼
                                React UI
```

------------------------------------------------------------------------

# 6. Repository Indexing Pipeline

The repository is indexed once per session.

``` text
Local Repository
       │
       ▼
Create Session Workspace
       │
       ▼
Copy/Load Repository
       │
       ▼
Identify Source Files
       │
       ▼
Tree-sitter Parsing
       │
       ▼
Extract Functions / Classes / Methods
       │
       ▼
Create Code Chunks + Metadata
       │
       ▼
Generate Embeddings
       │
       ▼
Build FAISS Index
       │
       ▼
Ready for Q&A / Code Review
```

Each indexed code unit should have metadata similar to:

``` text
file_path
symbol_name
symbol_type
language
start_line
end_line
code
```

Example:

``` text
file_path: src/auth/AuthService.py
symbol_name: authenticate_user
symbol_type: function
language: python
start_line: 42
end_line: 71
code: ...
```

The metadata is required so retrieved vectors can be mapped back to the
original source code.

------------------------------------------------------------------------

# 7. Repository Q&A

The user can ask questions such as:

``` text
How does authentication work?

Where is the database connection created?

Explain the payment flow.

Which file handles user authorization?

Where should I modify the code to add feature X?
```

The pipeline is:

``` text
User Question
      │
      ▼
Generate Query Embedding
      │
      ▼
FAISS Similarity Search
      │
      ▼
Top-K Relevant Code Chunks
      │
      ▼
Build Context
      │
      ▼
OpenAI LLM
      │
      ▼
Answer
```

The LLM receives:

``` text
User Question
+
Retrieved Code
+
Relevant Metadata
```

The entire repository should not be placed into the prompt unless there
is a specific future design reason to do so.

------------------------------------------------------------------------

# 8. RAG-Based Code Review

The initial project should use **RAG for code review**, rather than
sending only the changed code to the LLM.

The objective is to provide the LLM with relevant existing repository
context.

The general flow is:

``` text
Local Repository
       │
       ├───────────────┐
       │               │
       ▼               ▼
Repository Index    Local Code Changes
       │               │
       │               ▼
       │          Review Query/Context
       │               │
       └───────┬───────┘
               ▼
        FAISS Retrieval
               │
               ▼
      Relevant Repository Code
               │
               ▼
          OpenAI LLM
               │
               ▼
          Code Review
```

The review should consider:

-   The changed code
-   Relevant retrieved repository code
-   Existing surrounding implementation
-   Relevant tests when retrieved
-   File/function metadata

The review implementation should use the bounded LangGraph state
workflow described in the RAG/LLM Framework section. LangGraph coordinates
validation, shared-index retrieval, context sufficiency, LLM generation,
and finding validation; it does not execute repository code or apply
patches.

The LLM can then produce findings such as:

``` text
Severity
File
Line
Issue
Explanation
Suggested Fix
```

The exact review schema should remain simple and structured.

------------------------------------------------------------------------

# 9. Shared RAG Architecture

Repository Q&A and code review should use the **same underlying
repository index**.

``` text
                    Repository
                         │
                         ▼
                    Index Once
                         │
                         ▼
                       FAISS
                         │
              ┌──────────┴──────────┐
              │                     │
              ▼                     ▼
         User Question          Code Changes
              │                     │
              ▼                     ▼
       Query Embedding        Review Context
              │                     │
              └──────────┬──────────┘
                         ▼
                  FAISS Retrieval
                         │
                         ▼
                Relevant Code Chunks
                         │
                         ▼
                     OpenAI LLM
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
          Q&A Answer            Code Review
```

This is an explicit design decision.

Do NOT create separate vector stores or separate indexing pipelines for
Q&A and code review.

------------------------------------------------------------------------

# 10. Session Lifecycle

A session represents one temporary repository analysis environment.

Example:

``` text
POST /api/session
        │
        ▼
session_id = abc123
        │
        ▼
/tmp/codelens/abc123/
        │
        ├── repo/
        ├── index/
        └── metadata/
```

Then:

``` text
Index Repository
       ↓
Ask Questions
       ↓
Perform Code Reviews
       ↓
Session Ends
       ↓
Delete Temporary Data
```

The session should isolate repository data from other sessions.

------------------------------------------------------------------------

# 11. Suggested API Design

The API should remain simple.

## Create Session

``` http
POST /api/session
```

Response:

``` json
{
  "session_id": "abc123"
}
```

------------------------------------------------------------------------

## Upload/Provide Local Repository

The exact transport can be chosen during implementation based on the
simplest practical local-repository input mechanism.

Conceptually:

``` http
POST /api/session/{session_id}/repository
```

The endpoint initializes the repository in the session workspace and
starts indexing.

------------------------------------------------------------------------

## Ask Repository Question

``` http
POST /api/session/{session_id}/chat
```

Request:

``` json
{
  "question": "How does authentication work?"
}
```

Response should contain the answer and, where possible, relevant source
references.

------------------------------------------------------------------------

## Code Review

``` http
POST /api/session/{session_id}/review
```

The implementation should accept the local code-review context needed
for the review, such as a local git diff or selected changes.

The exact request format can be finalized during implementation.

------------------------------------------------------------------------

## Delete Session

``` http
DELETE /api/session/{session_id}
```

This removes the session's temporary repository, FAISS index, and
metadata.

------------------------------------------------------------------------

# 12. Suggested Backend Structure

A simple monolithic backend is preferred.

``` text
backend/
│
├── main.py
│
├── api/
│   ├── session.py
│   ├── repository.py
│   ├── chat.py
│   └── review.py
│
├── session/
│   └── manager.py
│
├── parser/
│   ├── tree_sitter_parser.py
│   └── chunker.py
│
├── embeddings/
│   └── embedder.py
│
├── retrieval/
│   ├── faiss_store.py
│   └── retriever.py
│
├── rag/
│   ├── qa.py
│   └── code_review.py
│
└── llm/
    └── client.py
```

The exact structure can change during implementation if a simpler
organization is more appropriate.

------------------------------------------------------------------------

# 13. Frontend Structure

A simple React application is sufficient.

Conceptually:

``` text
frontend/
│
├── src/
│   ├── components/
│   ├── pages/
│   ├── services/
│   ├── types/
│   └── App.tsx
```

The UI should provide at least:

1.  Local repository input
2.  Indexing/loading status
3.  Repository Q&A
4.  Code review
5.  Retrieved source references
6.  Review findings

Do not build a complex dashboard in V1.

------------------------------------------------------------------------

# 14. Important RAG Design Constraints

The RAG system should be code-aware.

Do not treat a repository as ordinary prose.

The indexing pipeline should preserve:

``` text
File
Function
Class
Method
Line numbers
Language
```

This enables answers such as:

``` text
Authentication is implemented in:

src/auth/AuthService.py
authenticate_user()
lines 42–71
```

rather than only returning a generic textual answer.

------------------------------------------------------------------------

# 15. Error Handling Requirements

The system should gracefully handle:

-   Invalid repository input
-   Unsupported/unknown file types
-   Empty repositories
-   Parsing failures
-   Embedding API failures
-   LLM API failures
-   Missing code-review changes
-   Session not found
-   Invalid session state

A single malformed source file should not necessarily prevent the entire
repository from being indexed.

------------------------------------------------------------------------

# 16. Security / Safety Considerations

Because the application processes arbitrary code:

-   Do not execute repository code during indexing.
-   Treat repository files as untrusted input.
-   Do not execute generated code or patches in V1.
-   Do not expose arbitrary server filesystem paths to the frontend.
-   Keep each session isolated.
-   Store API keys only through environment variables/configuration.
-   Clean up temporary repository data after the session.

------------------------------------------------------------------------

# 17. Explicitly Out of Scope for V1

The following should NOT be implemented initially:

``` text
❌ GitHub repository retrieval
❌ GitHub API integration
❌ PostgreSQL
❌ pgvector
❌ Redis
❌ Kafka
❌ Microservices
❌ Kubernetes
❌ Persistent user accounts
❌ Persistent chat history
❌ Persistent PR review history
❌ Persistent embeddings
❌ Complex multi-agent architecture
❌ Autonomous code modification
❌ Automatic patch application
❌ Execution of untrusted repository code
❌ Production-scale distributed processing
```

The goal is a clean, working RAG application.

------------------------------------------------------------------------

# 18. Future Development Phases

## Phase 1 --- Core Repository Q&A

Build:

``` text
Local Repository
       ↓
Parsing
       ↓
Chunking
       ↓
Embeddings
       ↓
FAISS
       ↓
RAG
       ↓
Repository Q&A
```

This should be the first working milestone.

------------------------------------------------------------------------

## Phase 2 --- RAG-Based Code Review

Add:

``` text
Local Repository
       +
Local Git Diff / Changes
       ↓
RAG Retrieval
       ↓
LLM
       ↓
Structured Code Review
```

Q&A and code review continue to use the same repository index.

------------------------------------------------------------------------

## Phase 3 --- UI Improvements

Improve:

-   Source references
-   Line-level references
-   Review finding display
-   Loading/progress states
-   Better repository navigation

Only add UI complexity when it improves the actual developer experience.

------------------------------------------------------------------------

## Phase 4 --- Persistence (Optional)

Introduce PostgreSQL only if persistent functionality is desired.

Potential features:

``` text
User accounts
Repository history
Chat history
Previous PR reviews
Persistent embeddings
Incremental indexing
```

pgvector may be introduced at this stage if persistent vector search is
required.

------------------------------------------------------------------------

## Phase 5 --- GitHub Integration (FINAL / DEFERRED)

**GitHub repository retrieval using the GitHub API is explicitly the
final phase.**

Only after the local-repository workflow is complete should the project
add:

``` text
GitHub Repository URL
        ↓
GitHub API
        ↓
Repository Retrieval
        ↓
Existing CodeLens Indexing Pipeline
```

The GitHub integration should reuse the existing indexing/RAG pipeline
rather than creating a separate architecture.

Potential future capabilities:

-   Import repository from GitHub URL
-   Retrieve PR metadata
-   Retrieve PR diffs
-   Review GitHub PRs directly
-   Potentially post review comments later

These are future extensions and are not part of the current core
implementation.

------------------------------------------------------------------------

# 19. Final V1 Architecture

The V1 architecture is intentionally limited to:

``` text
                    LOCAL REPOSITORY
                           │
                           ▼
                  Temporary Filesystem
                           │
                           ▼
                    Tree-sitter
                           │
                           ▼
             Functions / Classes / Chunks
                           │
                           ▼
                      Embeddings
                           │
                           ▼
                         FAISS
                           │
                  ┌────────┴────────┐
                  │                 │
                  ▼                 ▼
             Repository Q&A     Code Review
                  │                 │
                  └────────┬────────┘
                           ▼
                      OpenAI LLM
                           │
                           ▼
                    FastAPI Backend
                           │
                         REST
                           │
                           ▼
                  React + TypeScript UI
```

There is:

-   **No database**
-   **No GitHub retrieval**
-   **No persistent storage**
-   **No microservices**
-   **No Redis**
-   **No Kubernetes**
-   **No complex agent architecture**

The central technical concept is:

> **Parse the local repository into meaningful code units, embed them,
> retrieve relevant code using FAISS, and provide the retrieved context
> to an LLM through RAG for both repository Q&A and code review.**

------------------------------------------------------------------------

# 20. Design Principles for the Coding Agent

When implementing CodeLens, follow these principles:

1.  **Prefer simplicity over unnecessary abstraction.**
2.  **Do not introduce technologies not specified in this document
    without a clear reason.**
3.  **Keep the backend as a single FastAPI application.**
4.  **Keep repository/session data temporary.**
5.  **Do not introduce a database in V1.**
6.  **Use RAG for both Q&A and code review.**
7.  **Use the same repository index for both capabilities.**
8.  **Use Tree-sitter for meaningful code-aware chunking.**
9.  **Preserve file/function/class/line metadata with every chunk.**
10. **Use LangGraph for bounded code-review state orchestration without
    introducing multi-agent complexity.**
11. **Never send the entire repository to the LLM unless explicitly
    justified.**
12. **Do not execute arbitrary repository code.**
13. **Build the local-repository workflow completely before adding
    GitHub integration.**
14. **GitHub API repository retrieval is the final deferred phase.**
15. **Do not over-engineer for production scale; this is a fresher-level
    placement project.**
16. **Any architectural change should be deliberate and documented
    rather than introduced implicitly.**

------------------------------------------------------------------------

# 21. Current Technology Summary

  Component            V1 Choice
  -------------------- ------------------------------------------
  Frontend             React + TypeScript + Vite
  Backend              Python + FastAPI
  LLM                  OpenAI API
  Embeddings           OpenAI Embeddings
  Code Parser          Tree-sitter
  Vector Store         FAISS
  RAG                  LangChain
  Workflow             LangGraph for bounded code-review orchestration
  Storage              Temporary server filesystem
  Database             None
  API                  REST
  Repository Input     Local repository
  GitHub Retrieval     Deferred to final phase
  Persistent History   Not in V1
  Deployment           Keep simple; Docker only if needed later

------------------------------------------------------------------------

# 22. Project Success Criteria

V1 is considered successful when a user can:

1.  Provide a local repository.
2.  Successfully index its supported source code.
3.  Ask meaningful questions about the repository.
4.  Receive answers grounded in retrieved repository code.
5.  See relevant file/function/line references.
6.  Provide local code changes/diff for review.
7.  Receive an AI code review grounded in relevant repository context.
8.  Perform both Q&A and code review using the same RAG index.
9.  End the session and have temporary repository/index data cleaned up.

The project should demonstrate **practical RAG + code understanding +
backend engineering**, without unnecessary infrastructure.
