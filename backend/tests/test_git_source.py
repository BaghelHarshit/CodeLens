from pathlib import Path
from unittest.mock import patch

import pytest

from app.review.git_source import GitSourceError, latest_commit_diff

DIFF = """diff --git a/src/app.py b/src/app.py
--- a/src/app.py
+++ b/src/app.py
@@ -1,1 +1,2 @@
 def run():
+    return False
"""


def test_missing_git_metadata_is_safe(tmp_path: Path) -> None:
    with pytest.raises(GitSourceError) as error:
        latest_commit_diff(tmp_path)
    assert error.value.code == "GIT_METADATA_MISSING"
    assert str(tmp_path) not in error.value.message


def test_latest_commit_normalizes_and_validates_output(tmp_path: Path) -> None:
    results = [type("Result", (), {"returncode": 0, "stdout": ".git", "stderr": ""})(), type("Result", (), {"returncode": 0, "stdout": DIFF.replace("\n", "\r\n"), "stderr": ""})()]
    with patch("app.review.git_source.subprocess.run", side_effect=results) as run:
        assert latest_commit_diff(tmp_path) == DIFF
    assert run.call_args_list[1].kwargs["shell"] is False
    assert run.call_args_list[1].kwargs["cwd"] == tmp_path


def test_empty_and_malformed_commit_are_safe(tmp_path: Path) -> None:
    ok = type("Result", (), {"returncode": 0, "stdout": ".git", "stderr": ""})()
    with patch("app.review.git_source.subprocess.run", side_effect=[ok, type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()]):
        with pytest.raises(GitSourceError, match="latest Git commit contains no changes"):
            latest_commit_diff(tmp_path)
    with patch("app.review.git_source.subprocess.run", side_effect=[ok, type("Result", (), {"returncode": 0, "stdout": "not a diff", "stderr": "private"})()]):
        with pytest.raises(GitSourceError) as error:
            latest_commit_diff(tmp_path)
    assert error.value.code == "MALFORMED_LAST_COMMIT"
    assert "private" not in error.value.message
