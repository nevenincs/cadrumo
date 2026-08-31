"""A constant named for the repository root must resolve to the repository root.

Gates and tools locate their subject by walking up from their own file:
``Path(__file__).resolve().parents[N]``. The depth is correct for exactly one
location, and NOTHING enforces it. When a module moves, the arithmetic keeps
evaluating, keeps returning a real directory, and quietly names a different
tree. There is no exception and no error -- the gate simply starts asking its
question of the wrong corpus.

Three cases were found in one sweep, all from the same relocation campaign:
the identifier ratchet scanned ``dev/`` instead of the package and reported its
own anchors as missing; the corpus freshness gate searched two directories
ABOVE the repository, where its corpus does not exist, and reported every
artifact absent; and three packaging gates built a wheel from a directory with
no ``pyproject.toml``. Each had been passing or failing for a reason unrelated
to what it was written to check.

The property asserted here is narrow on purpose. Only constants NAMED for the
repository are judged, and they are judged against one fact: the repository is
the directory carrying ``pyproject.toml``. A root named for a package or for
``src`` legitimately points at many different depths, so those are out of
scope; widening the name match without a matching definition of "correct"
would trade this gate's precision for noise.

The corpus is derived by reading the source, so a module added tomorrow is
covered by existing, and a module that moves is caught by the move rather than
by whoever next reads its failure message.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from cadrumo.core.directory_scan import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

#: The scanned trees. Both hold gates that locate a subject by walking upward.
_SCANNED_TREES = ("src", "dev")

#: A directory is the repository root when it carries the project definition.
_REPOSITORY_MARKER = "pyproject.toml"

#: Frozen third-party snapshots are not ours to correct.
_EXCLUDED_PARTS = frozenset({"baseline-source-snapshot", ".venv", "__pycache__"})


def _repository_named(name: str) -> bool:
    """Report whether ``name`` claims to be the repository root."""
    upper = name.upper()
    return "REPO" in upper and "ROOT" in upper


def _upward_root(value: ast.expr, origin: Path) -> Path | None:
    """Fold ``Path(__file__).resolve().parents[N]`` into the path it names.

    Returns ``None`` for anything else, including a root read from an
    environment variable or handed in as a fixture: those do not carry the
    failure mode this gate exists for.
    """
    if not isinstance(value, ast.Subscript):
        return None
    container = value.value
    if not (isinstance(container, ast.Attribute) and container.attr == "parents"):
        return None
    if not (isinstance(value.slice, ast.Constant) and isinstance(value.slice.value, int)):
        return None
    if "__file__" not in ast.unparse(container.value):
        return None
    parents = origin.resolve().parents
    index = value.slice.value
    return parents[index] if index < len(parents) else None


def _declared_repository_roots() -> tuple[tuple[Path, str, Path | None], ...]:
    """Return every module-level repository-root constant and where it lands."""
    declared: list[tuple[Path, str, Path | None]] = []
    for tree_name in _SCANNED_TREES:
        for path in scan_directory(_REPOSITORY_ROOT / tree_name, pattern="*.py", recursive=True):
            if _EXCLUDED_PARTS & set(path.relative_to(_REPOSITORY_ROOT).parts):
                continue
            try:
                module = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):  # pragma: no cover - unparseable is another gate's subject
                continue
            for node in module.body:
                targets = (
                    [node.target]
                    if isinstance(node, ast.AnnAssign)
                    else node.targets
                    if isinstance(node, ast.Assign)
                    else []
                )
                for target in targets:
                    if not isinstance(target, ast.Name) or not _repository_named(target.id):
                        continue
                    if node.value is None:  # pragma: no cover - a bare annotation declares no path
                        continue
                    resolved = _upward_root(node.value, path)
                    if resolved is not None:
                        declared.append((path, target.id, resolved))
    return tuple(declared)


def test_every_repository_root_constant_lands_on_the_repository() -> None:
    """A relocated module must not keep asking its question of another tree."""
    declared = _declared_repository_roots()

    assert len(declared) > 30, (
        f"only {len(declared)} repository-root constants were discovered; the scan collapsed and would pass vacuously"
    )

    stray = [
        f"{path.relative_to(_REPOSITORY_ROOT).as_posix()}: {name} -> {resolved}"
        for path, name, resolved in declared
        if not (resolved / _REPOSITORY_MARKER).is_file()
    ]

    assert stray == [], (
        "constants named for the repository root that do not resolve to it. The "
        "parent depth is correct for one location only, so a moved module keeps "
        "returning a real directory that is the wrong one:\n  " + "\n  ".join(sorted(stray))
    )
