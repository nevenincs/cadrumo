"""Project-level test inventory shared by repo-wide ratchets on the dev side.

The counterpart of ``cadrumo.tests._inventory`` for the parts of the test
inventory that live outside the shipped package. Moved here from the src-side
inventory so no module under ``src/`` holds a path into the dev tree: a ratchet
that must walk the repository's development test roots lives on the dev side,
where that walk is native.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

from cadrumo.core.directory_scan import DirectoryEntryKind, scan_directory

from .._paths import REPO_ROOT

PROJECT_TEST_ROOTS: tuple[Path, ...] = (REPO_ROOT / "dev", REPO_ROOT / "docs")
"""Project-level test roots outside the ``src/cadrumo`` package tree."""

_PRUNE_DIRECTORY_NAMES: frozenset[str] = frozenset({"__pycache__", ".git", ".venv", ".pytest_cache"})


def _python_files(root: Path) -> tuple[Path, ...]:
    """Every ``.py`` file beneath ``root``, walked with the noise directories pruned."""
    found = []
    for entry in scan_directory(
        root,
        recursive=True,
        select=DirectoryEntryKind.FILES,
        prune_directories=_PRUNE_DIRECTORY_NAMES,
    ):
        if entry.name.endswith(".py"):
            found.append(entry)
    return tuple(sorted(found))


@cache
def project_test_modules() -> tuple[Path, ...]:
    """Return project-level ``test_*.py`` modules outside ``src/cadrumo``."""
    collected: set = set()
    for root in PROJECT_TEST_ROOTS:
        if not root.exists():
            continue
        collected.update(path for path in _python_files(root) if path.name.startswith("test_"))
    return tuple(sorted(collected))


@cache
def project_test_control_modules() -> tuple[Path, ...]:
    """Return project-level tests plus support/conftest modules outside ``src/cadrumo``."""
    modules = set(project_test_modules())
    for root in PROJECT_TEST_ROOTS:
        if not root.exists():
            continue
        for path in _python_files(root):
            if "__pycache__" in path.parts or path.name == "__init__.py":
                continue
            relative_parts = path.relative_to(root).parts
            if path.name == "conftest.py" or "tests" in relative_parts:
                modules.add(path)
    return tuple(sorted(modules))


def all_test_control_modules() -> tuple[Path, ...]:
    """Return package test-control modules plus the project-level set.

    Recomputed here rather than imported from the src-side inventory so the
    two halves of the census meet without either side naming the other's tree.
    """
    from cadrumo.tests import discover_test_control_modules

    return tuple(sorted(set(discover_test_control_modules()) | set(project_test_control_modules())))
