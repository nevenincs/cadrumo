"""Discover current test populations and interpret per-test pytest markers."""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path
from typing import Final

from cadrumo.core.directory_scan import scan_directory
from dev.first_party_source import TEST_DIRECTORY
from dev.source_tree import repository_files

from .lane_configuration import _UTF_8
from .lane_contracts import TestMarkers

#: Directories that never contain runnable project tests.
_PRUNED: Final[frozenset[str]] = frozenset(
    {".git", ".venv", "node_modules", "__pycache__", "_build", ".mypy_cache", ".ruff_cache", ".pytest_cache"},
)


def _marker_name(node: ast.AST) -> str | None:
    """Return the NAME of a ``pytest.mark.NAME`` node, called or bare.

    Both spellings of that node are read: the dotted ``pytest.mark.NAME`` and
    the ``from pytest import mark`` form ``mark.NAME``. Requiring the dotted
    one would narrow a class this declares whole, and the narrowing does not
    fail loudly: a marker dropped here does not make a test read as absent, it
    makes it read as SELECTED by every lane expression that negates the marker
    -- ``integration and not serial`` reports a serial test reachable once its
    ``serial`` is invisible. That is coverage claimed over something never
    measured, so the spelling is a disjunction rather than a requirement.
    """
    target = node.func if isinstance(node, ast.Call) else node
    if not isinstance(target, ast.Attribute):
        return None
    owner = target.value
    if isinstance(owner, ast.Attribute) and owner.attr == "mark":
        return target.attr
    if isinstance(owner, ast.Name) and owner.id == "mark":
        return target.attr
    return None


def _module_markers(tree: ast.Module) -> frozenset[str]:
    """Return the module-level ``pytestmark`` markers every test inherits."""
    found: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "pytestmark" for target in node.targets):
            continue
        values = node.value.elts if isinstance(node.value, ast.List | ast.Tuple) else [node.value]
        for value in values:
            name = _marker_name(value)
            if name is not None:
                found.add(name)
    return frozenset(found)


def marker_sets_in(path: Path) -> tuple[TestMarkers, ...] | None:
    """Return each test's EFFECTIVE markers, or None when the file is unreadable.

    Effective means module-level ``pytestmark`` plus any enclosing class's
    decorators plus the test function's own -- the set pytest itself resolves.
    Per test, never unioned across the file: one ``os_keychain`` test must not
    make its unit-marked siblings read as unreachable.

    Args:
        path: The test module to read.

    Returns:
        One entry per discovered test, or None when the file cannot be read.
        None is distinct from an empty tuple: absent (a peer staging a
        deletion) is not the same finding as present-with-no-tests.
    """
    try:
        tree = ast.parse(path.read_text(encoding=_UTF_8, errors="replace"))
    except (SyntaxError, ValueError, OSError):
        return None

    found: list[TestMarkers] = []

    def _walk(body: list[ast.stmt], inherited: frozenset[str]) -> None:
        for node in body:
            own = (
                frozenset(name for name in (_marker_name(d) for d in node.decorator_list) if name is not None)
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
                else frozenset()
            )
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith("test"):
                found.append(TestMarkers(test=node.name, markers=inherited | own))
            elif isinstance(node, ast.ClassDef):
                _walk(node.body, inherited | own)

    _walk(tree.body, _module_markers(tree))
    return tuple(found)


def _tracked_python_files(root: Path) -> tuple[Path, ...]:
    """Return every ``.py`` path the working tree admits, repository-relative.

    Derived from the tree itself rather than a version-control tool: every
    committed path plus every new path nobody has ignored, minus what the
    repository's own ``.gitignore`` files exclude (see
    :func:`dev.source_tree.repository_files`). A path absent from disk -- a
    peer's staged deletion of a whole test package -- is therefore simply not
    enumerated, rather than named and then failing to read.
    """
    return tuple(Path(entry) for entry in repository_files(root) if entry.endswith(".py"))


def tracked_test_files(root: Path) -> tuple[Path, ...]:
    """Return every discovered test module, repository-relative."""
    return tuple(path for path in _tracked_python_files(root) if path.name.startswith("test_"))


def _test_directories_of(paths: Iterable[Path]) -> tuple[str, ...]:
    """Return every directory in ``paths`` a test module could be collected from.

    Two sources unioned, because either alone leaves open the hole the other
    closes:

    * the parent of every ``test_*.py`` -- where tests live now;
    * every ``tests`` package holding any ``.py`` -- where a test lands
      tomorrow. A ``tests`` package carrying only ``__init__.py`` offers the
      file-level models nothing to report however orphaned it is, and it is the
      emptiest form of the defect: the first module written into it is
      collected by nobody, and the author learns that from a silent absence.
    """
    directories = {path.parent.as_posix() for path in paths if path.name.startswith("test_")}
    directories |= {path.parent.as_posix() for path in paths if path.parent.name == TEST_DIRECTORY}
    return tuple(sorted(directories))


def tracked_test_directories(root: Path) -> tuple[str, ...]:
    """Return every discovered directory a test module could be collected from."""
    return _test_directories_of(_tracked_python_files(root))


def expression_selects(expression: str | None, markers: frozenset[str]) -> bool:
    """Return whether a pytest ``-m`` expression can select these markers.

    Evaluated structurally rather than by string matching: ``unit or (integration
    and not serial)`` accepts a file marked integration only when it is not also
    marked serial, and that distinction is the whole reason the generator tests
    were unreachable.
    """
    if expression is None or not expression.strip():
        return True
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        # An unparseable expression is not evidence of reachability.
        return False

    def _evaluate(node: ast.AST) -> bool:
        if isinstance(node, ast.Expression):
            return _evaluate(node.body)
        if isinstance(node, ast.BoolOp):
            results = [_evaluate(value) for value in node.values]
            return all(results) if isinstance(node.op, ast.And) else any(results)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not _evaluate(node.operand)
        if isinstance(node, ast.Name):
            return node.id in markers
        if isinstance(node, ast.Constant):
            return bool(node.value)
        # An unmodelled construct must not be read as selection.
        return False

    return _evaluate(tree)


def discover_test_files(root: Path) -> tuple[Path, ...]:
    """Return every runnable test module under ``root``."""
    return scan_directory(root, pattern="test_*.py", recursive=True, prune_directories=_PRUNED)


def discover_test_directories(root: Path) -> tuple[str, ...]:
    """Return every on-disk directory under ``root`` a test module could come from.

    The on-disk counterpart of :func:`tracked_test_directories`, and injectable
    for the same reason :func:`discover_test_files` is: the detector proofs
    drive an isolated synthetic tree rather than the repository itself, and a
    gate whose teeth can only be shown against the real tree has no teeth to
    show.
    """
    files = scan_directory(root, pattern="*.py", recursive=True, prune_directories=_PRUNED)
    relative = tuple(path.relative_to(root) if path.is_absolute() else path for path in files)
    return _test_directories_of(relative)
