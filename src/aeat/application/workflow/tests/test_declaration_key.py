"""Anti-regression structural gate for the workflow declaration-pointer surface (DB-05).

Asserts that ``declaration_key`` and ``update_declaration_pointer`` each have
exactly one *production* definition across the :mod:`aeat.application.workflow`
package. The duplicate ``update_declaration_pointer`` that lived in ``_engine.py``
was collapsed onto the canonical ``_models.py`` definition (accepted contract); this gate
keeps the duplication from silently returning. It also pins the case-folding
contract: ``declaration_key`` upper-cases the period segment so a lowercase token
(``2025q1``) and its uppercase form (``2025Q1``) resolve to one canonical key.

Real-behavior AST walk over the package source — no mocks, no stubs.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from .. import declaration_key

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_WORKFLOW_DIR = Path(__file__).parent


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
    assert total == 1, (
        f"expected exactly one update_declaration_pointer definition, found {total}: {hits}"
    )


def test_declaration_key_period_is_case_insensitive() -> None:
    assert declaration_key("130", "2025q1") == declaration_key("130", "2025Q1")
    assert declaration_key("130", "2025q1") == "130:2025Q1"
