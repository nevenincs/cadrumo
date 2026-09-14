#!/usr/bin/env python
"""Fast, explicit-path Python repair for the immediate developer loop.

The caller supplies every file this command may mutate. Scope never comes
from Git, and omitted paths never expand to the repository. Remaining Ruff
or ty diagnostics are advisory after their safe fixes have been applied;
failure to invoke or configure a tool remains an operational failure.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

from dev._paths import REPO_ROOT
from dev.exit_codes import DRIFT, FINDINGS_CODES, FIX_STRICT_ENV, OK, TOOL_BROKEN, TOOL_MISSING

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

PYTHON_SUFFIXES: Final = frozenset({".py", ".pyi"})
NO_FINDINGS: Final[frozenset[int]] = frozenset[int]()

# The order is contractual: lint repair may create formatting work, and the
# formatter must see both Ruff's and ty's edits.
REPAIR_COMMANDS: Final[tuple[tuple[str, tuple[str, ...], frozenset[int]], ...]] = (
    ("ruff lint repair", ("uv", "run", "--no-sync", "ruff", "check", "--fix"), FINDINGS_CODES),
    ("ty repair", ("uv", "run", "--no-sync", "ty", "check", "--fix"), FINDINGS_CODES),
    ("ruff format", ("uv", "run", "--no-sync", "ruff", "format"), NO_FINDINGS),
)


def resolve_paths(raw_paths: Sequence[str], *, repo_root: Path = REPO_ROOT) -> tuple[Path, ...]:
    """Resolve explicit Python files and refuse any path outside the worktree."""
    root = repo_root.resolve(strict=True)
    resolved: list[Path] = []
    seen: set[Path] = set()
    for raw_path in raw_paths:
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = root / candidate
        path = candidate.resolve(strict=True)
        if not path.is_relative_to(root):
            raise ValueError(f"path is outside this worktree: {raw_path}")
        if not path.is_file() or path.suffix.lower() not in PYTHON_SUFFIXES:
            raise ValueError(f"path is not an eligible Python file: {raw_path}")
        if path not in seen:
            seen.add(path)
            resolved.append(path)
    if not resolved:
        raise ValueError("at least one explicit Python file is required")
    return tuple(resolved)


def _run(command: Sequence[str]) -> int:
    """Run one locked tool from the repository without environment sync."""
    try:
        return subprocess.run(command, cwd=REPO_ROOT, check=False).returncode
    except FileNotFoundError:
        return TOOL_MISSING
    except OSError:
        return TOOL_BROKEN


def _content_state(paths: Sequence[Path]) -> str:
    """Fingerprint only the validated files this invocation owns."""
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(str(path).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def repair(paths: Sequence[Path], *, runner: Callable[[Sequence[str]], int] = _run) -> int:
    """Apply the fixed repair sequence to already validated paths."""
    strict = bool(os.environ.get(FIX_STRICT_ENV))
    try:
        before = _content_state(paths) if strict else ""
    except OSError as exc:
        print(f"FAIL  could not read repair scope: {exc}", file=sys.stderr, flush=True)
        return TOOL_BROKEN
    path_args = tuple(str(path) for path in paths)
    for name, prefix, finding_codes in REPAIR_COMMANDS:
        command = (*prefix, "--", *path_args)
        print(f"$ {' '.join(command)}", flush=True)
        status = runner(command)
        if status == OK:
            continue
        if status in finding_codes:
            print(f"ADVISORY  {name} left diagnostics (exit {status})", file=sys.stderr, flush=True)
            continue
        print(f"FAIL  {name} could not complete (exit {status})", file=sys.stderr, flush=True)
        return status if status in {TOOL_MISSING, TOOL_BROKEN} else TOOL_BROKEN
    if strict:
        try:
            changed = _content_state(paths) != before
        except OSError as exc:
            print(f"FAIL  could not read repaired scope: {exc}", file=sys.stderr, flush=True)
            return TOOL_BROKEN
        if changed:
            print("fix-code repaired caller-owned files; commit the result.", file=sys.stderr, flush=True)
            return DRIFT
    return OK


def main(argv: Sequence[str] | None = None) -> int:
    """Validate caller-owned paths and run the bounded repair action."""
    parser = argparse.ArgumentParser(
        prog="python -m dev.quality.fixes",
        description="Repair explicitly named Python files without consulting or mutating Git state.",
    )
    parser.add_argument("paths", nargs="+", help="caller-owned .py or .pyi files inside this worktree")
    args = parser.parse_args(argv)
    try:
        paths = resolve_paths(args.paths)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return repair(paths)


if __name__ == "__main__":
    sys.exit(main())
