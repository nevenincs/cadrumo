"""Provisioning of `env/.env`.

`env/.env` is created from `env/.env.example` when it is absent, then topped up
from the worktree checked out on `main`, when that is a separate worktree with
its own `env/.env`. A value is ported when the operator set it there - it is
non-empty and differs from main's own template - and this worktree still holds
nothing or its template's value for that key. A value this worktree set for
itself is never overwritten, so running this again changes nothing.

The file holds the operator's secrets. Nothing here prints, logs, or raises a
value: every message names keys and counts only.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from dev._paths import REPO_ROOT
from dev.packaging.command_execution import run_command

#: The branch whose worktree holds the operator's established configuration.
MAIN_BRANCH: Final = "refs/heads/main"

GIT_TIMEOUT_SECONDS: Final = 30

#: `KEY=value`, optionally prefixed with `export`, as dotenv loaders read it.
_ASSIGNMENT: Final = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")


@dataclass(frozen=True)
class _Assignment:
    """One `KEY=value` line: its position, the text through `=`, and the raw value."""

    index: int
    prefix: str
    value: str


@dataclass
class Porting:
    """Which keys a porting pass changed, left alone, or could not handle."""

    ported: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def _read_lines(path: Path) -> list[str]:
    with path.open(encoding="utf-8", newline="") as handle:
        return handle.readlines()


def _assignments(lines: list[str]) -> dict[str, _Assignment]:
    """Return each key's last assignment, which is the one a dotenv loader keeps."""
    found: dict[str, _Assignment] = {}
    for index, line in enumerate(lines):
        text = line.rstrip("\r\n")
        match = _ASSIGNMENT.match(text)
        if match:
            found[match.group(1)] = _Assignment(index, text[: match.end()], text[match.end() :])
    return found


def _values(path: Path) -> dict[str, str]:
    return {key: line.value.strip() for key, line in _assignments(_read_lines(path)).items()}


def _is_empty(value: str) -> bool:
    return value.strip() in {"", '""', "''"}


def _is_multiline(value: str) -> bool:
    """Return whether a value opens a quote it does not close on the same line."""
    stripped = value.strip()
    quote = stripped[:1]
    return quote in {'"', "'"} and stripped.find(quote, 1) == -1


def _ending(line: str) -> str:
    return line[len(line.rstrip("\r\n")) :]


def _replace(target: Path, text: str) -> None:
    """Write ``text`` over ``target`` atomically, so an interrupted run never truncates it."""
    handle, temporary = tempfile.mkstemp(dir=target.parent, prefix=".env.", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as stream:
            stream.write(text)
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


def port_values(*, target: Path, template: Path, source: Path, source_template: Path) -> Porting:
    """Copy the values the operator set in ``source`` into ``target``.

    Args:
        target: This worktree's `env/.env`.
        template: This worktree's `env/.env.example`.
        source: The main worktree's `env/.env`.
        source_template: The main worktree's `env/.env.example`; a value equal
            to its default was never set by the operator and is not ported.

    Returns:
        The keys ported, kept because ``target`` set its own value, and skipped
        because a multi-line value cannot be ported line by line.
    """
    source_defaults = _values(source_template) if source_template.is_file() else {}
    defaults = _values(template)
    lines = _read_lines(target)
    current = _assignments(lines)
    newline = next((_ending(line) for line in lines if _ending(line)), "\n")
    appended: list[str] = []
    result = Porting()
    for key, line in _assignments(_read_lines(source)).items():
        _port_assignment(key, line, source_defaults, current, defaults, lines, newline, appended, result)
    if result.ported:
        if lines and not _ending(lines[-1]):
            lines[-1] += newline
        _replace(target, "".join(lines + appended))
    return result


def main_worktree(root: Path) -> Path | None:
    """Return the worktree checked out on `main`, when it is not ``root`` itself.

    Returns:
        Its path, or ``None`` when there is no such worktree, ``root`` is it, or
        git cannot answer.
    """
    git = shutil.which("git")
    if git is None:
        return None
    try:
        listing = run_command(
            [git, "--no-optional-locks", "worktree", "list", "--porcelain"],
            cwd=root,
            errors="replace",
            timeout_seconds=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if listing.returncode != 0:
        return None
    worktree: Path | None = None
    for line in listing.stdout.splitlines():
        key, _, value = line.partition(" ")
        if key == "worktree":
            worktree = Path(value)
        elif key == "branch" and value == MAIN_BRANCH and worktree is not None:
            return None if worktree.resolve() == root.resolve() else worktree
    return None


def provision(root: Path, main: Path | None) -> int:
    """Create `env/.env` when absent, then port the main worktree's values into it.

    Args:
        root: The worktree to provision.
        main: The worktree checked out on `main`, or ``None``.

    Returns:
        0 on success, 1 when the template is missing or the files cannot be
        read or written.
    """
    example = root / "env" / ".env.example"
    target = root / "env" / ".env"
    if not example.is_file():
        print("env/.env.example not found - cannot provision env/.env", file=sys.stderr, flush=True)
        return 1
    if target.exists():
        print("env/.env already exists - keeping every value it sets.", flush=True)
    else:
        shutil.copyfile(example, target)
        print("Created env/.env from env/.env.example.", flush=True)
    if main is None or not (main / "env" / ".env").is_file():
        print("No separate main worktree with an env/.env - nothing to port.", flush=True)
        return 0
    source = main / "env" / ".env"
    try:
        result = port_values(
            target=target,
            template=example,
            source=source,
            source_template=main / "env" / ".env.example",
        )
    except (OSError, UnicodeError):
        # The exception text is not echoed: a decode error can quote file content.
        print(
            f"Could not port env/.env values from {main}: a file is unreadable or not UTF-8.",
            file=sys.stderr,
            flush=True,
        )
        return 1
    if result.ported:
        print(f"Ported {len(result.ported)} value(s) from {main}: {', '.join(result.ported)}", flush=True)
    else:
        print(f"No new values to port from {main}.", flush=True)
    if result.kept:
        print(f"Kept {len(result.kept)} value(s) this worktree sets itself: {', '.join(result.kept)}", flush=True)
    if result.skipped:
        skipped = ", ".join(result.skipped)
        print(f"Skipped {len(result.skipped)} multi-line value(s); copy by hand: {skipped}", flush=True)
    return 0


def env_setup() -> int:
    """Provision this checkout's `env/.env`, porting values from the main worktree."""
    return provision(REPO_ROOT, main_worktree(REPO_ROOT))


def _port_assignment(
    key: str,
    line: _Assignment,
    source_defaults: dict[str, str],
    current: dict[str, _Assignment],
    defaults: dict[str, str],
    lines: list[str],
    newline: str,
    appended: list[str],
    result: Porting,
) -> None:
    """Port assignment."""
    value = line.value
    if _is_empty(value) or source_defaults.get(key) == value.strip():
        return
    mine = current.get(key)
    if _unportable_line_value(value, mine):
        result.skipped.append(key)
    elif mine is None:
        appended.append(f"{key}={value}{newline}")
        result.ported.append(key)
    elif mine.value.strip() == value.strip():
        return
    elif _target_holds_default(mine, defaults, key):
        lines[mine.index] = mine.prefix + value + (_ending(lines[mine.index]) or newline)
        result.ported.append(key)
    else:
        result.kept.append(key)


def _unportable_line_value(value: str, mine: _Assignment | None) -> bool:
    """Require both source and existing target values to be single-line before porting."""
    return _is_multiline(value) or (mine is not None and _is_multiline(mine.value))


def _target_holds_default(mine: _Assignment, defaults: dict[str, str], key: str) -> bool:
    """Permit replacement only of an empty target or its own template default."""
    return _is_empty(mine.value) or defaults.get(key) == mine.value.strip()
