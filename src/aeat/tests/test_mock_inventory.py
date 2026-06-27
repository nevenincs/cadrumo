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
from ._inventory import ast_for_path, discover_test_modules, repo_path, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_logger = get_logger(__name__)

# Documented boundary-mock sites.
# Format: (repo-relative path, module imported).
# Each entry requires a one-line justification comment here AND in the source.
_DOCUMENTED_BOUNDARY_MOCKS: frozenset[tuple[str, str]] = frozenset()

# Import module names that constitute banned test-control usage.
_FORBIDDEN_TEST_CONTROL_IMPORTS = ("unittest.mock", "unittest", "mock", "pytest_mock")


def _forbidden_test_control_imports(
    tree: ast.AST,
) -> list[tuple[int, str]]:
    """Return ``(lineno, module)`` for every banned test-control import in *tree*."""
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
    modules = discover_test_modules()
    violations: list[str] = []

    for module_path in modules:
        relative = repo_relative(module_path)
        tree = ast_for_path(module_path, source_tree_ast)
        if tree is None:
            continue
        for lineno, mock_module in _forbidden_test_control_imports(tree):
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
        path = repo_path(rel_path)
        assert path.exists(), f"Documented mock references non-existent file: {rel_path}"
        tree = ast_for_path(path)
        found = _forbidden_test_control_imports(tree) if tree is not None else []
        found_modules = {m for _, m in found}
        assert mock_module in found_modules, (
            f"Documented mock ({rel_path}, {mock_module!r}) is stale — "
            f"import not found in file (found: {sorted(found_modules)})"
        )


def test_discovery_found_modules() -> None:
    """Guardrail: the discovery walk must find at least one test module."""
    modules = discover_test_modules()
    assert modules, "No test modules discovered — check glob roots."
