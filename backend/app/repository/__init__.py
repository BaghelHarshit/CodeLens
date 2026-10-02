"""Safe local repository ingestion services."""

from .ingestion import IngestionError, IngestionResult, ingest_repository

__all__ = ["IngestionError", "IngestionResult", "ingest_repository"]
