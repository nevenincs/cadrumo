"""Real-behavior tests for the import-hygiene facade scanner.

Guards against the regression where ``discover_facades`` only recognised the
plain ``__all__ = [...]`` assignment form and silently failed to register any
``__init__.py`` using the annotated ``__all__: list[str] = [...]`` form as a
facade -- misclassifying every symbol already exported by that package as
"needs promotion" downstream.
"""

from __future__ import annotations

import ast

import pytest

from ..import_hygiene_scan import _dunder_all_assignment_value, discover_facades

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _parse_single_statement(src: str) -> ast.stmt:
    """Parse ``src`` (one module-level statement) and return its AST node."""
    module = ast.parse(src)
    (stmt,) = module.body
    return stmt


def test_dunder_all_assignment_value_recognises_plain_form() -> None:
    """The plain ``__all__ = [...]`` assignment must yield its list value."""
    node = _parse_single_statement('__all__ = ["Foo", "Bar"]')

    value = _dunder_all_assignment_value(node)

    assert isinstance(value, ast.List)
    assert [elt.value for elt in value.elts] == ["Foo", "Bar"]


def test_dunder_all_assignment_value_recognises_annotated_form() -> None:
    """The annotated ``__all__: list[str] = [...]`` form must also resolve."""
    node = _parse_single_statement('__all__: list[str] = ["Foo", "Bar"]')

    value = _dunder_all_assignment_value(node)

    assert isinstance(value, ast.List)
    assert [elt.value for elt in value.elts] == ["Foo", "Bar"]


def test_dunder_all_assignment_value_ignores_unrelated_annotated_assignment() -> None:
    """An annotated assignment to a name other than ``__all__`` is not matched."""
    node = _parse_single_statement('SOME_OTHER: list[str] = ["Foo"]')

    assert _dunder_all_assignment_value(node) is None


def test_dunder_all_assignment_value_ignores_bare_annotation_with_no_value() -> None:
    """A bare annotation with no assigned value (``__all__: list[str]``) is not a binding."""
    node = _parse_single_statement("__all__: list[str]")

    assert _dunder_all_assignment_value(node) is None


def test_discover_facades_registers_annotated_all_init_as_a_facade() -> None:
    """``aeat.core`` declares ``__all__`` in the annotated form and must be discovered.

    Exercises the real ``discover_facades`` walk over the actual ``src/aeat``
    tree (no fixtures, no mocks) so the regression -- ``aeat.core`` silently
    absent from the facade set -- is caught against the live source tree.
    """
    facades = discover_facades()

    assert "aeat.core" in facades
    core_facade = facades["aeat.core"]
    assert core_facade.has_real_all is True
    assert "Modelo" in core_facade.all_names
    assert "CasillaId" in core_facade.all_names
