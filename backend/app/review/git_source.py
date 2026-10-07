"""Safe extraction of the latest commit's unified diff."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .diff import parse_unified_diff
from .models import ReviewLimits, ReviewValidationError


class GitSourceError(RuntimeError):
    """A stable, non-sensitive failure while reading a local Git repository."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


_GIT_TIMEOUT_SECONDS = 10


def latest_commit_diff(repository_dir: Path, limits: ReviewLimits | None = None) -> str:
    """Return the latest commit patch without modifying or executing repository data."""
    if not repository_dir.is_dir() or repository_dir.is_symlink():
        raise GitSourceError("GIT_REPOSITORY_UNAVAILABLE", "The repository is unavailable.")

    try:
        _run_git(repository_dir, ["rev-parse", "--git-dir"], max_chars=4096)
    except GitSourceError as error:
        if error.code == "GIT_COMMAND_FAILED":
            raise GitSourceError(
                "GIT_METADATA_MISSING", "The uploaded repository does not contain Git metadata."
            ) from error
        raise

    try:
        diff = _run_git(
            repository_dir,
            ["show", "--format=", "--no-ext-diff", "--no-color", "--patch", "HEAD"],
            max_chars=(limits or ReviewLimits()).max_diff_chars,
        )
    except GitSourceError as error:
        if error.code == "GIT_DIFF_TOO_LARGE":
            raise
        raise GitSourceError(
            "GIT_COMMIT_UNAVAILABLE", "The latest Git commit is unavailable."
        ) from error

    diff = diff.replace("\r\n", "\n").replace("\r", "\n")
    if not diff.strip():
        raise GitSourceError("EMPTY_LAST_COMMIT", "The latest Git commit contains no changes.")
    try:
        parse_unified_diff(diff, limits)
    except ReviewValidationError as error:
        if "DIFF_TOO_LARGE" in str(error):
            raise GitSourceError(
                "GIT_DIFF_TOO_LARGE", "The latest Git commit diff is too large."
            ) from error
        raise GitSourceError(
            "MALFORMED_LAST_COMMIT", "The latest Git commit diff is invalid."
        ) from error
    return diff


def _run_git(repository_dir: Path, args: list[str], max_chars: int) -> str:
    """Run one fixed, read-only Git command with bounded output and no shell."""
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=repository_dir,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
            shell=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as error:
        code = (
            "GIT_TIMEOUT" if isinstance(error, subprocess.TimeoutExpired) else "GIT_COMMAND_FAILED"
        )
        message = (
            "Git did not respond in time."
            if code == "GIT_TIMEOUT"
            else "Git could not read the repository."
        )
        raise GitSourceError(code, message) from error
    if completed.returncode != 0:
        raise GitSourceError("GIT_COMMAND_FAILED", "Git could not read the repository.")
    output = completed.stdout
    if len(output) > max_chars:
        raise GitSourceError("GIT_DIFF_TOO_LARGE", "The latest Git commit diff is too large.")
    return output
