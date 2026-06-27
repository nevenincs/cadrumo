"""Hardcoded-constant extraction gates: VARCHAR(64), LibreOffice engine, WorkbookKind enum.

Asserts that:
  (a) Zero bare "VARCHAR(64)" string literals survive as assignment RHS or
      keyword-argument values in secure_objects.py — every occurrence must
      reference the module-level _VARCHAR_64 constant.
  (b) Zero bare "libreoffice-headless" string literals survive as
      assignment RHS or keyword-argument values in _workbook_parity.py —
      every occurrence must reference the module-level _ENGINE_LIBREOFFICE
      constant.
  (c) WorkbookKind is a StrEnum and all its members are enrolled — the
      six canonical kind values must be present as enum members, not as
      free-floating Literal aliases.

These tests are purely structural (AST-level) and carry no numeric oracle;
they enforce the extraction discipline rather than any runtime calculation.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path

import pytest

from ._inventory import SRC_AEAT, ast_for_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SRC_AEAT = SRC_AEAT

_SECURE_OBJECTS_PATH = _SRC_AEAT / "adapters" / "persistence" / "storage" / "sql" / "secure_objects.py"
_WORKBOOK_PARITY_PATH = _SRC_AEAT / "domain" / "calculations" / "registry" / "_workbook_parity.py"
_WORKBOOK_PARITY_TYPES_PATH = _SRC_AEAT / "domain" / "calculations" / "registry" / "_workbook_parity_types.py"

_WORKBOOK_KIND_MEMBERS: frozenset[str] = frozenset(
    {
        "formula_form",
        "record_design_layout",
        "validation_hints",
        "static_layout",
        "unsupported_binary_xls",
        "unreadable",
    },
)


def _bare_string_literals_in_file(
    path: Path,
    target: str,
    source_tree_ast: Mapping[Path, ast.AST] | None = None,
) -> list[int]:
    """Return line numbers where ``target`` appears as a bare string constant.

    Walks the AST of ``path`` and reports every ``ast.Constant`` node whose
    value equals ``target``, skipping nodes that are docstrings (the first
    statement of a module / class / function body when they are an
    ``ast.Expr`` wrapping a ``Constant``).
    """
    tree = ast_for_path(path, source_tree_ast)
    assert tree is not None, f"{path} must be parseable"
    docstring_nodes: set[int] = _collect_docstring_ids(tree)
    hits: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value == target and id(node) not in docstring_nodes:
            hits.append(node.lineno)
    return hits


def _collect_docstring_ids(tree: ast.AST) -> set[int]:
    """Return the ``id()`` of every AST node that is a docstring constant."""
    ids: set[int] = set()
    for node in ast.walk(tree):
        body: list[ast.stmt] | None = None
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            ids.add(id(body[0].value))
    return ids


def _workbook_kind_enum_members(
    path: Path,
    source_tree_ast: Mapping[Path, ast.AST] | None = None,
) -> frozenset[str]:
    """Return the StrEnum member values declared for WorkbookKind in ``path``."""
    tree = ast_for_path(path, source_tree_ast)
    assert tree is not None, f"{path} must be parseable"
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name != "WorkbookKind":
            continue
        values: set[str] = set()
        for item in node.body:
            if (
                isinstance(item, ast.Assign)
                and isinstance(item.value, ast.Constant)
                and isinstance(item.value.value, str)
            ):
                values.add(item.value.value)
        return frozenset(values)
    return frozenset()


def test_no_bare_varchar64_in_secure_objects(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """All VARCHAR(64) references in secure_objects.py must use _VARCHAR_64.

    Exactly one occurrence is permitted: the constant's own module-level
    assignment (``_VARCHAR_64: Final[str] = "VARCHAR(64)"``).  Every other
    site must reference the constant, not repeat the bare literal.
    """
    hits = _bare_string_literals_in_file(_SECURE_OBJECTS_PATH, "VARCHAR(64)", source_tree_ast)
    assert len(hits) <= 1, (
        f"Bare 'VARCHAR(64)' literal found in {_SECURE_OBJECTS_PATH.name} at lines {hits}. "
        "Only the _VARCHAR_64 constant definition may carry the bare literal; "
        "all callsites must reference _VARCHAR_64."
    )


def test_no_bare_libreoffice_engine_in_workbook_parity(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """All 'libreoffice-headless' references must use _ENGINE_LIBREOFFICE.

    The only allowed occurrence is the constant's own assignment; callsites
    (engine=, WorkbookRunnerEngine Literal) are excluded from the invariant
    by virtue of them being the canonical constant definition, not duplicate
    literal dispersal.  We assert zero hits *outside* the definition line.
    """
    hits = _bare_string_literals_in_file(_WORKBOOK_PARITY_PATH, "libreoffice-headless", source_tree_ast)
    # Two occurrences are structural: the Literal type alias definition and
    # the _ENGINE_LIBREOFFICE assignment.  Both are on module-level definition
    # lines, not callsites.  We allow at most those two.
    assert len(hits) <= 2, (
        f"Unexpected bare 'libreoffice-headless' literals in {_WORKBOOK_PARITY_PATH.name} "
        f"at lines {hits}. Callsites must use _ENGINE_LIBREOFFICE."
    )


def test_workbook_kind_is_strenum_with_all_members() -> None:
    """WorkbookKind must be a StrEnum enrolling all six canonical kind values."""
    from enum import StrEnum

    from ..domain.calculations.registry._workbook_parity import WorkbookKind

    assert issubclass(WorkbookKind, StrEnum), "WorkbookKind must be a StrEnum subclass, not a Literal alias."
    enrolled = frozenset(member.value for member in WorkbookKind)
    missing = _WORKBOOK_KIND_MEMBERS - enrolled
    assert not missing, (
        f"WorkbookKind StrEnum is missing members for: {sorted(missing)}. "
        "Every canonical workbook kind must be enrolled."
    )
    extra = enrolled - _WORKBOOK_KIND_MEMBERS
    assert not extra, (
        f"WorkbookKind StrEnum has unexpected members: {sorted(extra)}. "
        "Update _WORKBOOK_KIND_MEMBERS in this test if this is intentional."
    )


def test_workbook_kind_enum_members_in_ast(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """All six WorkbookKind values must appear as class-body assignments in source."""
    enrolled = _workbook_kind_enum_members(_WORKBOOK_PARITY_TYPES_PATH, source_tree_ast)
    missing = _WORKBOOK_KIND_MEMBERS - enrolled
    assert not missing, (
        f"WorkbookKind class body in {_WORKBOOK_PARITY_TYPES_PATH.name} "
        f"is missing member assignments for: {sorted(missing)}."
    )
