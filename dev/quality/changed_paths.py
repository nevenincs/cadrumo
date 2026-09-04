"""Verify the mechanical gates over only the paths a change touches.

The whole-tree static gates answer whether the tree is currently clean. That
question can only be asked usefully after a batch has landed, which is why
formatting and style drift is repeatedly noticed long after it was introduced.
This module asks the narrower question that is still actionable: did THIS
change leave the paths it touched clean?

It is a preflight, not a barrier. Nothing installs it into the commit path.
In a worktree with concurrent writers the enforcement position that would make
it binding is the same position whose stash-and-restore step has destroyed
uncommitted work here, so this deliberately stops short of it.

Safety properties, which are the reason it can be run freely:

* It manipulates no git state. The only git command issued is
  ``git diff --name-only``, which reads and writes nothing.
* It rewrites no file. Every underlying check runs in verify mode.
* Its cost is bounded by the size of the change rather than the size of the
  tree, so it is usable immediately before committing.

Scope is deliberately partial. Formatting, lint style and relative-import shape
all decompose to individual files, so they are checked here. Dependency
declaration does not -- it is a usage-versus-declaration predicate over the
whole tree -- and remains owned by the aggregate static gate.

Intended invocation:

* ``just check-changed`` -- uncommitted work against ``HEAD``.
* ``just check-changed BASE=origin/main`` -- a whole branch.
* ``python -m dev.quality.changed_paths [BASE]``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Final

from .._paths import REPO_ROOT

_RUFF: Final[tuple[str, ...]] = ("uv", "run", "--no-sync", "ruff")


def _git_lines(arguments: list[str], *, failure: str, repo_root: Path = REPO_ROOT) -> list[str]:
    """Run one read-only git query and return its non-empty output lines."""
    completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
        ["git", *arguments],  # noqa: S607 - repository tool is fixed
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or failure
        raise SystemExit(f"check-changed: {message}")
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def changed_python_paths(base: str, *, repo_root: Path = REPO_ROOT) -> tuple[Path, ...]:
    """Return the existing Python files that differ from ``base``.

    Untracked files are included alongside the diff. ``git diff`` reports
    only what git already knows about, so a change consisting entirely of
    NEW files produced an empty path set and the preflight exited 0 having
    checked nothing - reporting the change clean at the exact moment its
    files had never been looked at once.

    Ignored files stay out: ``--exclude-standard`` honours the same ignore
    rules the contributor already declared, so build output and caches do not
    become the preflight's problem.

    Deleted and renamed-away paths are dropped rather than reported: a check
    cannot speak about a file that is no longer there, and asking ruff to read
    one is an error about this module rather than about the change.
    """
    names = _git_lines(
        ["diff", "--name-only", base],
        failure=f"git diff against {base!r} failed",
        repo_root=repo_root,
    )
    names += _git_lines(
        ["ls-files", "--others", "--exclude-standard"],
        failure="git could not list the untracked files",
        repo_root=repo_root,
    )

    paths = set()
    for name in names:
        if not name.endswith(".py"):
            continue
        candidate = repo_root / name
        if candidate.is_file():
            paths.add(candidate)
    return tuple(sorted(paths))


def _run(label: str, argv: list[str]) -> bool:
    """Run one verify-mode check and report whether it passed."""
    completed = subprocess.run(argv, cwd=REPO_ROOT, capture_output=True, text=True, check=False)  # noqa: S603
    if completed.returncode == 0:
        return True
    sys.stdout.write(f"--- {label} ---\n")
    sys.stdout.write(completed.stdout)
    sys.stderr.write(completed.stderr)
    return False


def main(argv: list[str] | None = None) -> int:
    """Check the changed paths and return a process exit status."""
    arguments = sys.argv[1:] if argv is None else argv
    base = arguments[0] if arguments else "HEAD"

    paths = changed_python_paths(base)
    if not paths:
        return 0

    names = [str(path) for path in paths]
    outcomes = (
        _run("format", [*_RUFF, "format", "--check", *names]),
        _run("style", [*_RUFF, "check", *names]),
        _run(
            "relative-imports",
            [sys.executable, "-m", "dev.quality.relative_imports", *names],
        ),
    )
    return 0 if all(outcomes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
