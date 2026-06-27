"""Static guard: forbidden test-control import inventory for production tests.

Walks every ``test_*.py`` and ``_test_*.py`` module under ``src/aeat/`` via AST
and classifies each ``unittest`` / ``mock`` / ``pytest_mock`` import.

Classification rules:
- **Legitimate boundary mock**: the import is present to stub a third-party
  transport (Playwright browser session factory, mnemonic-decoding library
  function) where running the real implementation requires live external
  infrastructure that is deliberately excluded from unit tests.  Each site
  is documented in ``_DOCUMENTED_BOUNDARY_MOCKS``.
- **Drift**: any mock import not in the documented set.

Current inventory for durable replacement:
  Zero ``unittest``, ``mock``, or ``pytest_mock`` imports found under
  ``src/aeat/``.  The codebase uses constructor injection with inline
  callables for boundary-injection sites rather than the mock library.

The test asserts that no undocumented mock imports appear.  When a legitimate
boundary mock is added, an entry MUST be added to ``_DOCUMENTED_BOUNDARY_MOCKS``
with a one-line justification.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path

import pytest

from ..core.logging import get_logger

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_logger = get_logger(__name__)

_SRC_AEAT = Path(__file__).resolve().parent.parent
_REPO_ROOT = _SRC_AEAT.parents[1]  # chore-476-restructure-execution
_FIXTURES_DIR = _SRC_AEAT / "tests" / "fixtures"

# Documented boundary-mock sites.
# Format: (repo-relative path, module imported).
# Each entry requires a one-line justification comment here AND in the source.
_DOCUMENTED_BOUNDARY_MOCKS: frozenset[tuple[str, str]] = frozenset()

# Import module names that constitute banned test-control usage.
_FORBIDDEN_TEST_CONTROL_IMPORTS = ("unittest.mock", "unittest", "mock", "pytest_mock")


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


def _forbidden_test_control_imports(
    path: Path,
    tree: ast.AST | None = None,
) -> list[tuple[int, str]]:
    """Return ``(lineno, module)`` for every banned test-control import in *path*.

    When *tree* is supplied (test-loop path), reuse the cached AST. When
    omitted (single-file callers such as
    ``test_documented_boundary_mocks_still_present``), fall back to a
    per-call parse so the helper signature stays single-path compatible.
    """
    if tree is None:
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            return []

    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                hit = _forbidden_import_name(alias.name)
                if hit is not None:
                    hits.append((node.lineno, hit))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "unittest" and any(alias.name == "mock" for alias in node.names):
                hits.append((node.lineno, "unittest.mock"))
                continue
            hit = _forbidden_import_name(module)
            if hit is not None:
                hits.append((node.lineno, hit))
    return hits


def _forbidden_import_name(import_name: str) -> str | None:
    """Return the banned import prefix matched by *import_name*, if any."""
    for prefix in _FORBIDDEN_TEST_CONTROL_IMPORTS:
        if import_name == prefix or import_name.startswith(prefix + "."):
            return prefix
    return None


def test_mock_imports_are_documented(
    source_tree_ast: Mapping[Path, ast.AST],
) -> None:
    """Every banned test-control import must be in the documented boundary-mock inventory.

    Consumes the session-scoped AST cache; falls back to per-file parse
    for modules absent from the cache (e.g. unparseable files).
    """
    modules = _discover_test_modules()
    violations: list[str] = []

    for module_path in modules:
        relative = str(module_path.relative_to(_REPO_ROOT)).replace("\\", "/")
        tree = source_tree_ast.get(module_path)
        for lineno, mock_module in _forbidden_test_control_imports(module_path, tree):
            key = (relative, mock_module)
            if key in _DOCUMENTED_BOUNDARY_MOCKS:
                _logger.debug(
                    "documented boundary mock: %s:%d import %s",
                    relative,
                    lineno,
                    mock_module,
                )
                continue
            violations.append(f"{relative}:{lineno}: import {mock_module}")

    assert not violations, (
        "Undocumented banned test-control imports found "
        "(add to _DOCUMENTED_BOUNDARY_MOCKS with justification, or remove):\n" + "\n".join(violations)
    )


def test_documented_boundary_mocks_still_present() -> None:
    """Every entry in _DOCUMENTED_BOUNDARY_MOCKS must still appear in source."""
    for rel_path, mock_module in _DOCUMENTED_BOUNDARY_MOCKS:
        path = _REPO_ROOT / rel_path
        assert path.exists(), f"Documented mock references non-existent file: {rel_path}"
        found = _forbidden_test_control_imports(path)
        found_modules = {m for _, m in found}
        assert mock_module in found_modules, (
            f"Documented mock ({rel_path}, {mock_module!r}) is stale — "
            f"import not found in file (found: {sorted(found_modules)})"
        )


def test_discovery_found_modules() -> None:
    """Guardrail: the discovery walk must find at least one test module."""
    modules = _discover_test_modules()
    assert modules, "No test modules discovered — check glob roots."
