"""Anti-regression structural gate for the workflow declaration-pointer surface (DB-05).

Asserts that ``declaration_key`` and ``update_declaration_pointer`` each have
exactly one *production* definition across the :mod:`aeat.application.workflow`
package. The duplicate ``update_declaration_pointer`` that lived in ``_engine.py``
was collapsed onto the canonical ``_models.py`` definition; this gate
keeps the duplication from silently returning. It also pins the typed key
contract: ``declaration_key`` stores the filing year and bare registry token
as separate key segments, never as a combined token such as ``2025Q1``.

Real-behavior AST walk over the package source — no mocks, no stubs.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, cast

import pytest

from ....core import Period
from .. import WorkflowState, declaration_key, update_declaration_pointer

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_WORKFLOW_DIR = Path(__file__).parents[1]


def _production_def_count(name: str) -> dict[str, int]:
    """Return ``{filename: count}`` of ``def <name>`` across production package modules.

    Test modules (``test_*.py``) and ``conftest.py`` are excluded so the gate
    measures production duplication only.
    """
    hits: dict[str, int] = {}
    for path in sorted(_WORKFLOW_DIR.glob("*.py")):
        if path.name.startswith("test_") or path.name == "conftest.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        count = sum(
            1
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
        )
        if count:
            hits[path.name] = count
    return hits


def test_declaration_key_has_exactly_one_definition() -> None:
    hits = _production_def_count("declaration_key")
    total = sum(hits.values())
    assert total == 1, f"expected exactly one declaration_key definition, found {total}: {hits}"


def test_update_declaration_pointer_has_exactly_one_definition() -> None:
    """DB-05: the _engine duplicate was collapsed onto the _models canonical (contract)."""
    hits = _production_def_count("update_declaration_pointer")
    total = sum(hits.values())
    assert total == 1, f"expected exactly one update_declaration_pointer definition, found {total}: {hits}"


def test_declaration_key_uses_separated_period_identity() -> None:
    period = Period.from_year_and_code(2025, "1T")

    assert declaration_key("130", period) == "130:2025:1T"


def test_declaration_key_rejects_combined_string_period() -> None:
    combined_period = cast(Any, "2025Q1")
    with pytest.raises(TypeError, match=r"aeat\.core\.Period"):
        declaration_key("130", combined_period)


def test_update_declaration_pointer_uses_typed_period_key() -> None:
    period = Period.from_year_and_code(2025, "1T")

    state = update_declaration_pointer(
        WorkflowState(),
        modelo="130",
        period=period,
        draft_id="d" * 64,
        status="BORRADOR",
    )

    assert set(state.declarations) == {"130:2025:1T"}
    pointer = state.declarations["130:2025:1T"]
    assert pointer.period == period
    assert pointer.draft_id == "d" * 64
