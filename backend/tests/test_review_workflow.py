import json

import pytest

from app.indexing import IndexingRegistry, SearchResult
from app.llm import FakeLLM, LLMGenerationError, LLMRefusalError
from app.review import (
    ReviewWorkflowError,
    normalize_review_response,
    parse_unified_diff,
    run_review_workflow,
)
from app.chunking.models import CodeChunk


DIFF = """diff --git a/src/app.py b/src/app.py
--- a/src/app.py
+++ b/src/app.py
@@ -1,1 +1,2 @@
 def run():
+    return False
"""


def ready_registry() -> IndexingRegistry:
    chunk = CodeChunk(
        chunk_id="related",
        relative_path="tests/test_app.py",
        symbol_name="test_run",
        symbol_type="function",
        language="python",
        source="assert run()",
        start_line=1,
        end_line=1,
        parent_start_line=1,
        parent_end_line=1,
    )

    class Index:
        ready = True

        def search(self, query: str, top_k: int) -> list[SearchResult]:
            return [SearchResult(0.9, chunk)]

    registry = IndexingRegistry()
    registry._indexes["session"] = Index()  # type: ignore[assignment]
    return registry


def test_workflow_returns_grounded_findings() -> None:
    response = json.dumps(
        {
            "findings": [
                {
                    "severity": "high",
                    "file": "src/app.py",
                    "line": 2,
                    "issue": "The new return value is unsafe.",
                    "explanation": "The changed branch returns a false value.",
                }
            ]
        }
    )
    result = run_review_workflow(
        session_id="session", diff=DIFF, registry=ready_registry(), llm=FakeLLM(response)
    )
    assert result.outcome == "findings"
    assert result.findings[0].line == 2


def test_workflow_handles_no_findings_and_insufficient_context() -> None:
    no_findings = run_review_workflow(
        session_id="session", diff=DIFF, registry=ready_registry(), llm=FakeLLM('{"findings":[]}')
    )
    assert no_findings.outcome == "no_findings"

    class EmptyIndex:
        ready = True

        def search(self, query: str, top_k: int) -> list[SearchResult]:
            return []

    registry = IndexingRegistry()
    registry._indexes["session"] = EmptyIndex()  # type: ignore[assignment]
    llm = FakeLLM()
    result = run_review_workflow(session_id="session", diff=DIFF, registry=registry, llm=llm)
    assert result.outcome == "insufficient_context"
    assert llm.calls == []


def test_workflow_rejects_malformed_and_ungrounded_output() -> None:
    with pytest.raises(ReviewWorkflowError, match="MALFORMED_LLM_OUTPUT"):
        run_review_workflow(
            session_id="session", diff=DIFF, registry=ready_registry(), llm=FakeLLM("not json")
        )

    review = parse_unified_diff(DIFF)
    from app.review.context import ReviewContext

    with pytest.raises(ValueError, match="changed line"):
        normalize_review_response(
            '{"findings":[{"severity":"low","file":"src/app.py","line":1,"issue":"x","explanation":"y"}]}',
            review,
            ReviewContext((), "context", (), ()),
        )


def test_workflow_maps_provider_failures_safely() -> None:
    with pytest.raises(ReviewWorkflowError, match="LLM_FAILED"):
        run_review_workflow(
            session_id="session",
            diff=DIFF,
            registry=ready_registry(),
            llm=FakeLLM(error=LLMGenerationError("secret prompt")),
        )
    with pytest.raises(ReviewWorkflowError, match="LLM_FAILED"):
        run_review_workflow(
            session_id="session",
            diff=DIFF,
            registry=ready_registry(),
            llm=FakeLLM(refusal=True),
        )
