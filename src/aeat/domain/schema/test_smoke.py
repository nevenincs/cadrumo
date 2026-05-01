"""Smoke tests for :mod:`aeat.domain.schema`.

Enforces three invariants at test-collection time:

- The public surface matches the declared ``__all__`` tuple.
- Every name in ``__all__`` is actually importable from the package
  root.
- No module under ``src/aeat/schema/`` imports :mod:`aeat.domain.casillas`
  (strict dependency direction).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ...core import errors, logging
from . import __all__ as schema_all
from . import __doc__ as schema_doc
from . import __file__ as schema_file
from . import __name__ as _package_name

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_SCHEMA_DIR = Path(schema_file).parent
_FORBIDDEN_ROOTS: frozenset[str] = frozenset({"aeat.domain.casillas"})


def test_smoke_schema_docstring_and_base_error() -> None:
    """The package is importable and canonical conventions hold."""
    assert schema_doc is not None
    assert issubclass(errors.AeatError, Exception)
    assert logging.get_logger(__name__).name == __name__


def test_all_exports_importable() -> None:
    """Every name listed in ``__all__`` is present on the module."""
    import importlib

    package = importlib.import_module(_package_name)
    for name in schema_all:
        assert hasattr(package, name), f"missing export: {name}"


def test_no_imports_of_aeat_casillas_from_schema() -> None:
    """AST-scan every .py file under ``src/aeat/schema`` for banned imports."""
    violations: list[str] = []
    for path in sorted(_SCHEMA_DIR.rglob("*.py")):
        try:
            tree = ast.parse(path.read_bytes(), filename=str(path))
        except SyntaxError as exc:
            violations.append(f"{path}: syntax error: {exc}")
            continue
        for node in ast.walk(tree):
            modules_seen: list[str] = []
            if isinstance(node, ast.Import):
                modules_seen.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                modules_seen.append(node.module)
            for module in modules_seen:
                for forbidden in _FORBIDDEN_ROOTS:
                    if module == forbidden or module.startswith(forbidden + "."):
                        violations.append(f"{path}: imports forbidden module {module}")
    assert not violations, "\n".join(violations)
