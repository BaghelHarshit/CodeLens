"""Run all credential-free CodeLens quality gates."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"


def command(program: str, *args: str) -> list[str]:
    """Resolve a tool from the active environment on every platform."""

    if program in {"ruff", "mypy", "pytest"}:
        return [sys.executable, "-m", program, *args]
    return [program, *args]


def run(label: str, args: list[str], cwd: Path) -> int:
    """Run one gate and return its process status."""

    print(f"\n==> {label}", flush=True)
    result = subprocess.run(args, cwd=cwd, check=False)
    if result.returncode:
        print(f"FAILED: {label} (exit code {result.returncode})", flush=True)
    return result.returncode


def main() -> int:
    """Run backend and frontend checks without provider credentials."""

    npm = "npm.cmd" if os.name == "nt" else "npm"
    gates = [
        ("backend tests", command("pytest", "-c", "pyproject.toml", "tests"), BACKEND),
        ("backend format", command("ruff", "format", "--check", "app", "tests"), BACKEND),
        ("backend lint", command("ruff", "check", "app", "tests"), BACKEND),
        ("backend types", command("mypy", "app"), BACKEND),
        ("frontend typecheck", [npm, "run", "typecheck"], FRONTEND),
        ("frontend build", [npm, "run", "build"], FRONTEND),
        ("frontend lint", [npm, "run", "lint"], FRONTEND),
        ("frontend tests", [npm, "test", "--", "--run"], FRONTEND),
    ]
    for label, args, cwd in gates:
        status = run(label, args, cwd)
        if status:
            return status
    print("\nAll quality gates passed.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
