import pytest

from app.review import (
    ReviewFinding,
    ReviewResult,
    ReviewValidationError,
    Severity,
    parse_unified_diff,
)

DIFF = """diff --git a/src/app.py b/src/app.py
--- a/src/app.py
+++ b/src/app.py
@@ -1,2 +1,3 @@
 def run():
-    return False
+    value = True
+    return value
"""


def test_parse_unified_diff_normalizes_files_hunks_and_lines() -> None:
    parsed = parse_unified_diff(DIFF)

    assert parsed.schema_version == "review-v1"
    assert parsed.files[0].path == "src/app.py"
    assert parsed.files[0].hunks[0].lines[1].kind == "deletion"
    assert parsed.files[0].hunks[0].lines[2].new_line == 2
    assert parsed.to_dict()["files"][0]["hunks"][0]["new_count"] == 3


def test_parse_rejects_empty_malformed_unsafe_and_oversized_diffs() -> None:
    for value in ("", "not a diff", DIFF.replace("a/src/app.py", "a/../app.py")):
        with pytest.raises(ReviewValidationError):
            parse_unified_diff(value)

    with pytest.raises(ReviewValidationError, match="DIFF_TOO_LARGE"):
        parse_unified_diff(
            DIFF,
            limits=__import__("app.review", fromlist=["ReviewLimits"]).ReviewLimits(
                max_diff_chars=3
            ),
        )


def test_findings_and_terminal_results_are_versionable() -> None:
    finding = ReviewFinding(
        severity=Severity.HIGH,
        file="src/app.py",
        line=2,
        issue="Mutable state changes behavior.",
        explanation="The new value changes the return path.",
        suggested_fix="Keep the original invariant.",
        category="correctness",
        confidence=0.9,
    )
    result = ReviewResult("findings", (finding,))

    assert result.to_dict()["findings"][0]["severity"] == "high"
    with pytest.raises(ReviewValidationError):
        ReviewFinding(Severity.LOW, "src/app.py", 0, "issue", "explanation")
    with pytest.raises(ReviewValidationError):
        ReviewResult("findings")
