"""Static guard: zero ``pytest.mark.skip`` / ``pytest.mark.xfail`` in production tests.

Walks every ``test_*.py`` and ``_test_*.py`` module under ``src/aeat/`` via AST
and asserts that none carry ``pytest.mark.skip``, ``pytest.mark.skipif``, or
``pytest.mark.xfail`` decorators.

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

# Documented exceptions: (relative-to-repo path, marker name, justification).
# Additions here require a follow-up remediation note and inline justification in the
# source file.
_DOCUMENTED_EXCEPTIONS: frozenset[tuple[str, str]] = frozenset(
    {
        (
            "src/aeat/core/observability/tests/test_sink.py",
            "skipif",
        ),
    },
)

_FORBIDDEN_MARKERS = frozenset({"skip", "skipif", "xfail"})


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
    """Return ``(lineno, marker_name)`` for every forbidden marker in *path*."""
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []

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
            hits.append((dec.lineno, attr_chain.attr))
    return hits


def test_no_skip_or_xfail_markers() -> None:
    """Production test modules must not use skip / xfail markers."""
    modules = _discover_test_modules()
    violations: list[str] = []

    for module_path in modules:
        relative = str(module_path.relative_to(_REPO_ROOT)).replace("\\", "/")
        sites = _forbidden_marker_sites(module_path)
        for lineno, marker_name in sites:
            key = (relative, marker_name)
            if key in _DOCUMENTED_EXCEPTIONS:
                _logger.debug(
                    "skip/xfail exception allowed: path=%s, marker=%s, lineno=%d",
                    relative,
                    marker_name,
                    lineno,
                )
                continue
            violations.append(f"{relative}:{lineno}: @pytest.mark.{marker_name}")

    assert not violations, (
        "Undocumented pytest.mark.skip / skipif / xfail found "
        "(add to _DOCUMENTED_EXCEPTIONS with a durable rationale, or remove):\n" + "\n".join(violations)
    )


def test_documented_exceptions_all_exist() -> None:
    """Every entry in _DOCUMENTED_EXCEPTIONS must still be present in source."""
    for rel_path, marker_name in _DOCUMENTED_EXCEPTIONS:
        path = _REPO_ROOT / rel_path
        assert path.exists(), f"Documented exception references non-existent file: {rel_path}"
        sites = _forbidden_marker_sites(path)
        found_markers = {m for _, m in sites}
        assert marker_name in found_markers, (
            f"Documented exception ({rel_path}, {marker_name!r}) is stale — "
            f"marker not found in file (found: {sorted(found_markers)})"
        )


def test_discovery_found_modules() -> None:
    """Guardrail: the discovery walk must find at least one test module."""
    modules = _discover_test_modules()
    assert modules, "No test modules discovered — check glob roots."
