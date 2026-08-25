"""Import and public-surface contracts for the operator-surface facade."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_lazy_public_names_have_exact_static_owner_bindings() -> None:
    """Static imports mirror runtime owners without changing lazy imports."""
    from ... import operator_surface

    facade_tree = ast.parse(Path(operator_surface.__file__).read_text(encoding="utf-8"))
    type_checking_block = next(
        statement
        for statement in facade_tree.body
        if isinstance(statement, ast.If)
        and isinstance(statement.test, ast.Name)
        and statement.test.id == "TYPE_CHECKING"
    )
    static_owners = {
        alias.asname or alias.name: "." * statement.level + (statement.module or "")
        for statement in type_checking_block.body
        if isinstance(statement, ast.ImportFrom)
        for alias in statement.names
    }

    assert static_owners == operator_surface._EXPORT_MODULES
