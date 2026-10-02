"""FAISS-backed, session-scoped code chunk index."""

from __future__ import annotations

import json
import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import faiss
import numpy as np

from ..chunking.models import CodeChunk
from ..embeddings.protocol import EmbeddingProvider


class IndexValidationError(ValueError):
    """Raised when index input or persisted artifacts are invalid."""


@dataclass(frozen=True, slots=True)
class SearchResult:
    """A retrieved chunk and its similarity score."""

    score: float
    chunk: CodeChunk


class SessionIndex:
    """Build, persist, reload, and search one FAISS index in a session directory."""

    _INDEX_FILE = "vectors.faiss"
    _METADATA_FILE = "metadata.json"
    _VERSION = 1

    def __init__(self, index_dir: str | Path, provider: EmbeddingProvider) -> None:
        self.index_dir = Path(index_dir).resolve()
        self.provider = provider
        self._index: faiss.Index | None = None
        self._chunks: tuple[CodeChunk, ...] = ()

    @property
    def dimensions(self) -> int:
        return self.provider.dimensions

    @property
    def count(self) -> int:
        return len(self._chunks)

    @property
    def ready(self) -> bool:
        return self._index is not None and bool(self._chunks)

    def build(self, chunks: list[CodeChunk] | tuple[CodeChunk, ...]) -> None:
        """Embed chunks and atomically persist a new index."""
        if not chunks:
            raise IndexValidationError("cannot build an empty index")
        values = tuple(chunks)
        vectors = self.provider.embed_documents([chunk.source for chunk in values])
        matrix = self._validated_matrix(vectors, len(values))
        faiss.normalize_L2(matrix)
        index = faiss.IndexFlatIP(self.dimensions)
        index.add(matrix)
        self._persist(index, values)
        self._index = index
        self._chunks = values

    def load(self) -> None:
        """Load and validate persisted artifacts from this session directory."""
        index_path = self.index_dir / self._INDEX_FILE
        metadata_path = self.index_dir / self._METADATA_FILE
        if not index_path.is_file() or not metadata_path.is_file():
            raise IndexValidationError("index artifacts are missing")
        try:
            index = faiss.read_index(str(index_path))
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            chunks = tuple(CodeChunk.from_dict(item) for item in payload["chunks"])
            if payload["version"] != self._VERSION or payload["dimensions"] != self.dimensions:
                raise IndexValidationError("index metadata version or dimensions are invalid")
            if index.d != self.dimensions or index.ntotal != len(chunks):
                raise IndexValidationError("index and metadata counts or dimensions differ")
        except IndexValidationError:
            raise
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise IndexValidationError("index artifacts are invalid") from error
        self._index = index
        self._chunks = chunks

    def search(self, query: str, top_k: int) -> list[SearchResult]:
        """Return up to top_k stable, metadata-rich nearest chunks."""
        if self._index is None or not self._chunks:
            raise IndexValidationError("index is not ready")
        if top_k < 1:
            raise IndexValidationError("top_k must be positive")
        vector = self._validated_matrix([self.provider.embed_query(query)], 1)
        faiss.normalize_L2(vector)
        scores, positions = self._index.search(vector, min(top_k, self.count))
        results = [
            SearchResult(float(score), self._chunks[int(position)])
            for score, position in zip(scores[0], positions[0], strict=True)
            if 0 <= position < self.count and math.isfinite(float(score))
        ]
        return sorted(results, key=lambda item: (-item.score, item.chunk.chunk_id))

    def _validated_matrix(self, vectors: list[list[float]], expected: int) -> np.ndarray:
        if len(vectors) != expected or any(
            len(vector) != self.dimensions
            or any(not math.isfinite(float(value)) for value in vector)
            for vector in vectors
        ):
            raise IndexValidationError("embedding dimensions or values are invalid")
        return np.asarray(vectors, dtype=np.float32)

    def _persist(self, index: faiss.Index, chunks: tuple[CodeChunk, ...]) -> None:
        self.index_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": self._VERSION,
            "dimensions": self.dimensions,
            "chunks": [chunk.to_dict() for chunk in chunks],
        }
        with tempfile.TemporaryDirectory(dir=self.index_dir) as temporary:
            directory = Path(temporary)
            faiss.write_index(index, str(directory / self._INDEX_FILE))
            (directory / self._METADATA_FILE).write_text(
                json.dumps(payload, separators=(",", ":"), ensure_ascii=False), encoding="utf-8"
            )
            os.replace(directory / self._INDEX_FILE, self.index_dir / self._INDEX_FILE)
            os.replace(directory / self._METADATA_FILE, self.index_dir / self._METADATA_FILE)
