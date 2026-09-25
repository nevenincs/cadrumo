"""Run the blocking semgrep diff scan without touching the caller's worktree.

``just check-security-diff`` used to hand semgrep's own ``--baseline-commit``
implementation the live repository. Semgrep 1.168.0 implements that flag by
``git reset --hard <baseline>`` in the target directory, scanning, then
``git reset --hard <original HEAD>`` to restore it. In a worktree shared with
other sessions -- this repository's normal development mode -- that silently
discarded every other session's uncommitted work for the duration of the
scan, and a reset racing a concurrent edit could restore over it incorrectly.
The reflog carried six such reset pairs before this was traced to semgrep
rather than to any command this repository runs directly.

The fix moves the reset somewhere a reset cannot hurt anyone: a throwaway
``git worktree add --detach`` checkout of the same ``HEAD``, entirely outside
the caller's working tree. Semgrep resets that checkout instead, the checkout
is always removed afterward (even on failure), and the caller's tree -- and
every other session's -- is never touched. The merge-base, the config, the
scan target, and the ``--error`` gating semantics are unchanged from the
previous direct invocation; only where the reset lands has moved.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Final

from dev._paths import REPO_ROOT, UTF_8
from dev.exit_codes import TOOL_BROKEN

__all__ = [
    "DEFAULT_BASE",
    "DEFAULT_SEMGREP_ARGV",
    "SEMGREP_CONFIG",
    "SEMGREP_TARGET",
    "SEMGREP_VERSION",
    "SecurityDiffScanError",
    "main",
    "merge_base",
    "run_diff_scan",
]


class SecurityDiffScanError(RuntimeError):
    """A git or semgrep step needed to run the diff scan could not complete."""


#: Pinned in lockstep with ``check-security-full`` in the justfile.
SEMGREP_VERSION: Final[str] = "1.168.0"

#: Matches the previous direct invocation exactly.
SEMGREP_CONFIG: Final[str] = ".semgrep/rules/"
SEMGREP_TARGET: Final[str] = "src/cadrumo/"

DEFAULT_BASE: Final[str] = "origin/main"

DEFAULT_SEMGREP_ARGV: Final[tuple[str, ...]] = (
    "uvx",
    "--from",
    f"semgrep=={SEMGREP_VERSION}",
    "semgrep",
)

_GIT_TIMEOUT_SECONDS: Final[int] = 60


def _require_git() -> str:
    git = shutil.which("git")
    if git is None:
        raise SecurityDiffScanError("git executable not found on PATH")
    return git


def merge_base(base: str, *, root: Path = REPO_ROOT, git: str | None = None) -> str:
    """Return the merge-base commit of ``base`` and ``HEAD`` in ``root``."""
    git = git or _require_git()
    try:
        completed = subprocess.run(
            [git, "--no-optional-locks", "merge-base", base, "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            encoding=UTF_8,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except subprocess.CalledProcessError as error:
        raise SecurityDiffScanError(f"git merge-base {base} HEAD failed: {error.stderr.strip() or error}") from error
    return completed.stdout.strip()


def _add_scratch_worktree(git: str, worktree_dir: Path, *, root: Path) -> None:
    try:
        subprocess.run(
            [git, "--no-optional-locks", "worktree", "add", "--detach", str(worktree_dir), "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            encoding=UTF_8,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except subprocess.CalledProcessError as error:
        raise SecurityDiffScanError(
            f"git worktree add --detach {worktree_dir} HEAD failed: {error.stderr.strip() or error}"
        ) from error


def _remove_scratch_worktree(git: str, worktree_dir: Path, *, root: Path) -> None:
    """Best-effort cleanup. Runs from a ``finally`` block, so it never raises."""
    subprocess.run(
        [git, "--no-optional-locks", "worktree", "remove", "--force", str(worktree_dir)],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding=UTF_8,
        timeout=_GIT_TIMEOUT_SECONDS,
    )
    # Drops any admin metadata left behind if the remove above could not run
    # (for example the directory was already gone), so a scratch worktree
    # never lingers in `git worktree list`.
    subprocess.run(
        [git, "--no-optional-locks", "worktree", "prune"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding=UTF_8,
        timeout=_GIT_TIMEOUT_SECONDS,
    )
    shutil.rmtree(worktree_dir, ignore_errors=True)


def run_diff_scan(
    base: str = DEFAULT_BASE,
    *,
    root: Path = REPO_ROOT,
    semgrep_argv: tuple[str, ...] = DEFAULT_SEMGREP_ARGV,
    config: str = SEMGREP_CONFIG,
    target: str = SEMGREP_TARGET,
) -> int:
    """Run the baseline-scoped semgrep scan in a scratch worktree; return its exit code.

    ``root`` is read only: its ``HEAD`` is checked out elsewhere and nothing
    in ``root`` is reset, staged, or otherwise mutated. The scratch worktree
    is removed before this returns, on every exit path.
    """
    git = _require_git()
    baseline = merge_base(base, root=root, git=git)

    scratch_parent = Path(tempfile.mkdtemp(prefix="cadrumo-security-diff-"))
    # `git worktree add` must create the leaf directory itself.
    worktree_dir = scratch_parent / uuid.uuid4().hex
    try:
        _add_scratch_worktree(git, worktree_dir, root=root)
        command = [*semgrep_argv, "--config", config, "--error", target, "--baseline-commit", baseline]
        completed = subprocess.run(command, cwd=worktree_dir)
        return completed.returncode
    finally:
        _remove_scratch_worktree(git, worktree_dir, root=root)
        shutil.rmtree(scratch_parent, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: ``python -m dev.ci.security_diff_scan [BASE]``."""
    parser = argparse.ArgumentParser(
        prog="security-diff-scan",
        description="Run the blocking semgrep scan scoped to the diff since BASE, in a scratch worktree.",
    )
    parser.add_argument("base", nargs="?", default=DEFAULT_BASE, help="baseline ref, default origin/main")
    args = parser.parse_args(argv)

    try:
        return run_diff_scan(args.base)
    except SecurityDiffScanError as error:
        print(f"ERROR: security diff scan could not complete: {error}", file=sys.stderr)
        return TOOL_BROKEN


if __name__ == "__main__":
    raise SystemExit(main())
