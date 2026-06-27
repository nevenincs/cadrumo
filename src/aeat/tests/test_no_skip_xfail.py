"""Static guard: zero skip / xfail shortcuts in deterministic production tests.

Walks every ``test_*.py`` and ``_test_*.py`` module under ``src/aeat/`` via AST
and asserts that deterministic modules carry no ``pytest.mark.skip``,
``pytest.mark.skipif``, ``pytest.mark.xfail``, ``pytest.skip()``, or
``pytest.xfail()`` shortcuts.

Documented legitimate exceptions (environment-conditional guards):
- ``src/aeat/core/observability/tests/test_sink.py`` — ``@pytest.mark.skipif(
  sys.platform == "win32", ...)`` guards a file-permission test that requires
  POSIX chmod semantics; the guard is platform-conditional, not a behaviour
  mask.

Each exception MUST be accompanied by an inline justification comment in the
source file.  The exception set is the authoritative inventory; additions
require a corresponding durable remediation note.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ..core.logging import get_logger

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_logger = get_logger(__name__)

_SRC_AEAT = Path(__file__).resolve().parents[1]
_REPO_ROOT = _SRC_AEAT.parents[1]  # chore-476-restructure-execution
_FIXTURES_DIR = _SRC_AEAT / "tests" / "fixtures"

# Documented exceptions: (relative-to-repo path, marker/call name, justification).
# Additions here require a follow-up remediation note and inline justification in the
# source file.
_DOCUMENTED_EXCEPTIONS: frozenset[tuple[str, str]] = frozenset(
    {
        (
            "src/aeat/core/observability/tests/test_sink.py",
            "pytest.mark.skipif",
        ),
    },
)

_FORBIDDEN_MARKERS = frozenset({"skip", "skipif", "xfail"})
_FORBIDDEN_CALLS = frozenset({"pytest.skip", "pytest.xfail"})
_LIVE_EXECUTION_MARKER = "aeat_live"


def _discover_test_modules() -> list[Path]:
    globs = ("**/test_*.py", "**/_test_*.py")
    collected: set[Path] = set()
    for glob in globs:
        for path in _SRC_AEAT.glob(glob):
            if path.name == "__init__.py":
                continue
            try:
                path.relative_to(_FIXTURES_DIR)
            except ValueError:
                collected.add(path)
    return sorted(collected)


def _forbidden_marker_sites(path: Path) -> list[tuple[int, str]]:
    """Return ``(lineno, marker_or_call_name)`` for every forbidden shortcut in *path*."""
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []

    live_module = _LIVE_EXECUTION_MARKER in _module_execution_markers(tree)
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        decorators: list[ast.expr] = []
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            decorators = node.decorator_list

        for dec in decorators:
            # Accept both ``@pytest.mark.skip`` and ``@pytest.mark.skip(...)``
            attr_chain = dec.func if isinstance(dec, ast.Call) else dec
            if not isinstance(attr_chain, ast.Attribute):
                continue
            if attr_chain.attr not in _FORBIDDEN_MARKERS:
                continue
            mark_attr = attr_chain.value
            if not isinstance(mark_attr, ast.Attribute) or mark_attr.attr != "mark":
                continue
            mark_root = mark_attr.value
            if not isinstance(mark_root, ast.Name) or mark_root.id != "pytest":
                continue
            hits.append((dec.lineno, f"pytest.mark.{attr_chain.attr}"))

        if isinstance(node, ast.Call):
            call_name = _qualified_name(node.func)
            if call_name not in _FORBIDDEN_CALLS:
                continue
            if call_name == "pytest.skip" and live_module:
                continue
            hits.append((node.lineno, call_name))
    return hits


def _module_execution_markers(tree: ast.AST) -> set[str]:
    """Return module-level execution markers from a ``pytestmark = [...]`` assignment."""
    markers: set[str] = set()
    body = tree.body if isinstance(tree, ast.Module) else ()
    for node in body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "pytestmark" for target in node.targets):
            continue
        values: list[ast.expr] = list(node.value.elts) if isinstance(node.value, ast.List | ast.Tuple) else [node.value]
        for value in values:
            name = _qualified_name(value)
            if name.startswith("pytest.mark."):
                markers.add(name.removeprefix("pytest.mark."))
    return markers


def _qualified_name(node: ast.AST) -> str:
    """Return a dotted qualified name for simple AST name/attribute chains."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _qualified_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def test_no_skip_or_xfail_shortcuts() -> None:
    """Deterministic production test modules must not use skip / xfail shortcuts."""
    modules = _discover_test_modules()
    violations: list[str] = []

    for module_path in modules:
        relative = str(module_path.relative_to(_REPO_ROOT)).replace("\\", "/")
        sites = _forbidden_marker_sites(module_path)
        for lineno, marker_or_call_name in sites:
            key = (relative, marker_or_call_name)
            if key in _DOCUMENTED_EXCEPTIONS:
                _logger.debug(
                    "skip/xfail exception allowed: path=%s, marker_or_call=%s, lineno=%d",
                    relative,
                    marker_or_call_name,
                    lineno,
                )
                continue
            violations.append(f"{relative}:{lineno}: {marker_or_call_name}")

    assert not violations, (
        "Undocumented pytest skip / xfail shortcuts found "
        "(add to _DOCUMENTED_EXCEPTIONS with a durable rationale, or remove):\n" + "\n".join(violations)
    )


def test_documented_exceptions_all_exist() -> None:
    """Every entry in _DOCUMENTED_EXCEPTIONS must still be present in source."""
    for rel_path, marker_or_call_name in _DOCUMENTED_EXCEPTIONS:
        path = _REPO_ROOT / rel_path
        assert path.exists(), f"Documented exception references non-existent file: {rel_path}"
        sites = _forbidden_marker_sites(path)
        found_markers = {m for _, m in sites}
        assert marker_or_call_name in found_markers, (
            f"Documented exception ({rel_path}, {marker_or_call_name!r}) is stale — "
            f"marker not found in file (found: {sorted(found_markers)})"
        )


def test_discovery_found_modules() -> None:
    """Guardrail: the discovery walk must find at least one test module."""
    modules = _discover_test_modules()
    assert modules, "No test modules discovered — check glob roots."
