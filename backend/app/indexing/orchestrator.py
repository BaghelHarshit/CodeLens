"""Repository indexing pipeline and safe progress summaries."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from threading import RLock

from ..chunking import chunk_parsed_symbols
from ..config import Settings
from ..discovery import discover_source_files
from ..embeddings import EmbeddingProvider, create_embedding_provider
from ..parser import parse_discovered_files
from ..session.models import Session, SessionState
from .index import SessionIndex


@dataclass(slots=True)
class IndexStatus:
    """Public indexing state without source or filesystem details."""

    session_id: str
    state: str = SessionState.INDEXING.value
    stage: str = "queued"
    progress: int = 0
    files_seen: int = 0
    files_discovered: int = 0
    symbols_parsed: int = 0
    chunks_indexed: int = 0
    skipped_files: int = 0
    warnings: list[str] = field(default_factory=list)
    retries: int = 0
    error_code: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class IndexingRegistry:
    """Thread-safe session status and pipeline coordinator."""

    def __init__(
        self, provider_factory: Callable[[Settings], EmbeddingProvider] = create_embedding_provider
    ):
        self._statuses: dict[str, IndexStatus] = {}
        self._indexes: dict[str, SessionIndex] = {}
        self._lock = RLock()
        self._provider_factory = provider_factory

    def start(self, session: Session, settings: Settings) -> None:
        with self._lock:
            current = self._statuses.get(session.session_id)
            if current is not None and current.state == SessionState.INDEXING.value:
                raise RuntimeError("indexing is already in progress")
            self._statuses[session.session_id] = IndexStatus(session.session_id)
        try:
            self._run(session, settings)
        except Exception:
            with self._lock:
                status = self._statuses[session.session_id]
                status.state = SessionState.FAILED.value
                status.stage = "failed"
                status.progress = 100
                status.error_code = "INDEXING_FAILED"
                status.error_message = "The repository could not be indexed."
            if session.state is SessionState.INDEXING:
                session.state = SessionState.FAILED
            return
        with self._lock:
            self._statuses[session.session_id].state = SessionState.READY.value
            self._statuses[session.session_id].stage = "complete"
            self._statuses[session.session_id].progress = 100
        if session.state is SessionState.INDEXING:
            session.state = SessionState.READY

    def status(self, session_id: str) -> IndexStatus | None:
        with self._lock:
            value = self._statuses.get(session_id)
            if value is None:
                return None
            return IndexStatus(
                session_id=value.session_id,
                state=value.state,
                stage=value.stage,
                progress=value.progress,
                files_seen=value.files_seen,
                files_discovered=value.files_discovered,
                symbols_parsed=value.symbols_parsed,
                chunks_indexed=value.chunks_indexed,
                skipped_files=value.skipped_files,
                warnings=list(value.warnings),
                retries=value.retries,
                error_code=value.error_code,
                error_message=value.error_message,
            )

    def index(self, session_id: str) -> SessionIndex | None:
        with self._lock:
            return self._indexes.get(session_id)

    def _run(self, session: Session, settings: Settings) -> None:
        self._update(session.session_id, "discovery", 10)
        discovery = discover_source_files(session, settings)
        self._update(
            session.session_id,
            "parsing",
            30,
            files_seen=discovery.files_seen,
            files_discovered=len(discovery.files),
            skipped_files=sum(item.count for item in discovery.skipped),
            warnings=[f"{item.reason}: {item.count}" for item in discovery.skipped],
        )
        parsed = parse_discovered_files(session, discovery)
        self._update(
            session.session_id,
            "chunking",
            50,
            symbols_parsed=len(parsed.symbols),
            warnings=[item.code for item in parsed.diagnostics],
        )
        chunked = chunk_parsed_symbols(parsed)
        if not chunked.chunks:
            raise ValueError("no usable source chunks")
        self._update(session.session_id, "embedding", 70)
        index = SessionIndex(session.index_dir, self._provider_factory(settings))
        index.build(chunked.chunks)
        with self._lock:
            self._indexes[session.session_id] = index
            self._statuses[session.session_id].chunks_indexed = index.count
        self._update(session.session_id, "ready", 90)

    def _update(self, session_id: str, stage: str, progress: int, **values: object) -> None:
        with self._lock:
            status = self._statuses[session_id]
            status.stage = stage
            status.progress = progress
            for key, value in values.items():
                setattr(status, key, value)
