"""Deterministic provider doubles for offline tests."""

from app.embeddings.fake import FakeEmbeddings
from app.llm.fake import FakeLLM

__all__ = ["FakeEmbeddings", "FakeLLM"]
