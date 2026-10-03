from app.chunking.models import CodeChunk
from app.indexing import IndexingRegistry, SearchResult
from app.review import ReviewContextLimits, build_review_context, parse_unified_diff


DIFF = """diff --git a/src/app.py b/src/app.py
--- a/src/app.py
+++ b/src/app.py
@@ -1,2 +1,3 @@
 def run():
-    return False
+    value = True
+    return value
"""


def test_review_context_keeps_changed_code_and_related_indexed_context() -> None:
    changed = parse_unified_diff(DIFF)
    related = CodeChunk(
        chunk_id="test-chunk",
        relative_path="tests/test_app.py",
        symbol_name="test_run",
        symbol_type="function",
        language="python",
        source="def test_run():\n    assert run()",
        start_line=1,
        end_line=2,
        parent_start_line=1,
        parent_end_line=2,
    )

    class Index:
        ready = True
        calls: list[str] = []

        def search(self, query: str, top_k: int) -> list[SearchResult]:
            self.calls.append(query)
            return [SearchResult(0.9, related)]

    index = Index()
    registry = IndexingRegistry()
    registry._indexes["session"] = index  # type: ignore[assignment]

    result = build_review_context(session_id="session", review=changed, registry=registry)

    assert result.changed[0].path == "src/app.py"
    assert result.changed[0].hunks[0]["lines"][2]["new_line"] == 2
    assert result.references[0].relative_path == "tests/test_app.py"
    assert "return value" in result.changed[0].hunks[0]["lines"][3]["content"]
    assert any("Related tests" in query for query in index.calls)
    assert result.to_dict()["insufficient_context"] is False


def test_review_context_deduplicates_and_bounds_related_context() -> None:
    changed = parse_unified_diff(DIFF)
    chunk = CodeChunk(
        chunk_id="same",
        relative_path="src/related.py",
        symbol_name="helper",
        symbol_type="function",
        language="python",
        source="x" * 200,
        start_line=1,
        end_line=1,
        parent_start_line=1,
        parent_end_line=1,
    )

    class Index:
        ready = True

        def search(self, query: str, top_k: int) -> list[SearchResult]:
            return [SearchResult(0.8, chunk), SearchResult(0.7, chunk)]

    registry = IndexingRegistry()
    registry._indexes["session"] = Index()  # type: ignore[assignment]
    result = build_review_context(
        session_id="session",
        review=changed,
        registry=registry,
        limits=ReviewContextLimits(max_context_chars=80, max_references=1),
    )

    assert len(result.references) == 1
    assert len(result.context) <= 80


def test_review_context_can_contain_changed_only_when_retrieval_is_empty() -> None:
    changed = parse_unified_diff(DIFF)

    class EmptyIndex:
        ready = True

        def search(self, query: str, top_k: int) -> list[SearchResult]:
            return []

    registry = IndexingRegistry()
    registry._indexes["session"] = EmptyIndex()  # type: ignore[assignment]
    result = build_review_context(session_id="session", review=changed, registry=registry)

    assert result.insufficient
    assert result.references == ()
    assert result.changed
    assert result.context == ""
