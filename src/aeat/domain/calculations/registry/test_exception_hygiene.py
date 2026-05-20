"""Exception-handling hygiene tests for registry production modules."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


_REGISTRY_PACKAGE = Path(__file__).parent


def _production_modules() -> tuple[Path, ...]:
    return tuple(
        sorted(
            path
            for path in _REGISTRY_PACKAGE.glob("*.py")
            if not path.name.startswith("test_") and path.name != "conftest.py"
        )
    )


def test_registry_production_code_does_not_swallow_exceptions_with_pass() -> None:
    """A caught exception must be handled, converted, logged, or re-raised."""

    offenders: list[str] = []
    for path in _production_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                relative = path.relative_to(_REGISTRY_PACKAGE)
                offenders.append(f"{relative}:{node.lineno}")

    assert offenders == []


def test_registry_production_code_does_not_use_contextlib_suppress() -> None:
    """Suppressing exceptions hides registry drift; use an explicit typed result."""

    offenders: list[str] = []
    for path in _production_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.With):
                continue
            for item in node.items:
                context_expr = item.context_expr
                if isinstance(context_expr, ast.Call):
                    context_expr = context_expr.func
                if isinstance(context_expr, ast.Attribute) and context_expr.attr == "suppress":
                    relative = path.relative_to(_REGISTRY_PACKAGE)
                    offenders.append(f"{relative}:{node.lineno}")
                if isinstance(context_expr, ast.Name) and context_expr.id == "suppress":
                    relative = path.relative_to(_REGISTRY_PACKAGE)
                    offenders.append(f"{relative}:{node.lineno}")

    assert offenders == []
