"""Every git invocation against the working repository declines optional locks.

The repository is a shared worktree edited by several processes at once.  A
read-only command such as ``git status`` still takes ``index.lock`` to refresh
cached stat data, and a process interrupted mid-refresh leaves the lock behind,
refusing every later commit until someone removes it by hand.  Passing the
global ``--no-optional-locks`` option makes such reads lock-free.

The scan is per module: every module that resolves or spells the git executable
routes its calls through one helper, so the option appearing in the module is
the helper carrying it.  Modules that only ever run git inside a repository they
created themselves are listed with that reason, and a listed module that stops
invoking git fails the scan so the list cannot outlive its reason.
"""

from __future__ import annotations

import ast
from pathlib import PurePosixPath
from typing import Final

import pytest

from dev._paths import REPO_ROOT, UTF_8
from dev.source_tree import repository_files

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_LOCK_FREE_OPTION: Final = "--no-optional-locks"

#: Modules whose git invocations target a repository they created, never the
#: working one, so an interrupted run cannot strand the shared index lock.
_OWN_REPOSITORY_ONLY: Final[dict[str, str]] = {
    "dev/packaging/smoke_homebrew.py": "initialises, commits and pulls inside a temporary tap repository it creates",
    "dev/env/tests/test_clean.py": "builds a temporary fixture repository under tmp_path and runs git only there",
    "dev/ci/tests/test_security_diff_scan.py": "builds a fixture repository under tmp_path and runs git only there",
    "dev/packaging/tests/test_smoke_homebrew.py": "the only git-shaped literal is the Homebrew formula name ['git']",
}


def _is_git_constant(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value == "git"


def invokes_git(source: str) -> bool:
    """Return whether ``source`` resolves or spells the git executable."""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            function = node.func
            if (
                isinstance(function, ast.Attribute)
                and function.attr == "which"
                and node.args
                and _is_git_constant(node.args[0])
            ):
                return True
        if isinstance(node, (ast.List, ast.Tuple)) and node.elts and _is_git_constant(node.elts[0]):
            return True
    return False


def declines_optional_locks(source: str) -> bool:
    """Return whether ``source`` passes git the lock-free global option."""
    return any(
        isinstance(node, ast.Constant) and node.value == _LOCK_FREE_OPTION for node in ast.walk(ast.parse(source))
    )


def _python_sources() -> dict[str, str]:
    files = repository_files(REPO_ROOT, under=("dev", "src"))
    return {
        relative: (REPO_ROOT / relative).read_text(encoding=UTF_8)
        for relative in files
        if PurePosixPath(relative).suffix == ".py"
    }


def test_every_git_invoking_module_declines_optional_locks() -> None:
    sources = _python_sources()
    offenders = sorted(
        relative
        for relative, source in sources.items()
        if relative not in _OWN_REPOSITORY_ONLY and invokes_git(source) and not declines_optional_locks(source)
    )
    assert offenders == [], f"git invoked without {_LOCK_FREE_OPTION}: {offenders}"


def test_every_own_repository_exemption_still_invokes_git() -> None:
    sources = _python_sources()
    stale = sorted(
        relative for relative in _OWN_REPOSITORY_ONLY if relative not in sources or not invokes_git(sources[relative])
    )
    assert stale == [], f"exemptions that no longer invoke git: {stale}"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ('import shutil\nshutil.which("git")\n', True),
        ('run(["git", "status"])\n', True),
        ('run(("git", "diff"))\n', True),
        ('text = \'subprocess.run(["git", "grep"])\'\n', False),
        ('shutil.which("python")\n', False),
    ],
)
def test_invocation_detection(source: str, *, expected: bool) -> None:
    assert invokes_git(source) is expected


def test_a_lock_taking_invocation_is_detected() -> None:
    unsafe = 'import shutil\ngit = shutil.which("git")\nrun([git, "status", "--porcelain=v1"])\n'
    safe = 'import shutil\ngit = shutil.which("git")\nrun([git, "--no-optional-locks", "status"])\n'
    assert invokes_git(unsafe) and not declines_optional_locks(unsafe)
    assert invokes_git(safe) and declines_optional_locks(safe)
