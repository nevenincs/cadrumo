"""Focused contract tests for keyed-family field, member, clear, and order deltas."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.schema import ModeloRevision

from ..compiler.loader import load_modelo_directory
from .test_restated_family_merge import (
    _BASE_FORMULA,
    _CUOTA_FORMULA,
    _RECARGO_FORMULA,
    _SUCCESSOR,
    _build_modelo,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _successor(root: Path, declaration: str) -> ModeloRevision:
    return load_modelo_directory(_build_modelo(root, successor_extra=declaration)).revisions[_SUCCESSOR]


def test_changed_member_authors_only_its_changed_nested_field(tmp_path: Path) -> None:
    revision = _successor(
        tmp_path,
        '[[revisions."2025".family_overrides]]\n'
        'family = "formulas"\n'
        'selector = { revision = "2024", id = "modelo-999-cuota" }\n'
        'fields = { expression = { literal = "7" } }\n',
    )

    formula = next(item for item in revision.formulas if item.id == _CUOTA_FORMULA)
    assert formula.expression.literal == 7
    assert str(formula.target_casilla_id) == "0002"


def test_member_removal_addition_and_order_are_exact(tmp_path: Path) -> None:
    revision = _successor(
        tmp_path,
        '[[revisions."2025".family_removals]]\n'
        'family = "formulas"\n'
        'selector = { revision = "2024", id = "modelo-999-cuota" }\n'
        '[[revisions."2025".family_positions]]\n'
        'family = "formulas"\n'
        'id = "modelo-999-recargo"\n'
        "position = 0\n",
    )

    assert tuple(item.id for item in revision.formulas) == (_RECARGO_FORMULA, _BASE_FORMULA)


def test_explicit_clear_differs_from_omitted_family(tmp_path: Path) -> None:
    inherited = _successor(tmp_path / "inherited", "")
    modelo = _build_modelo(tmp_path / "cleared", successor_extra='cleared_families = ["constructs"]\n')
    successor_construct = next((modelo / "revisions" / _SUCCESSOR / "constructs").glob("*.toml"))
    successor_construct.unlink()
    successor_construct.parent.rmdir()
    cleared = load_modelo_directory(modelo).revisions[_SUCCESSOR]

    assert len(inherited.constructs) == 2
    assert cleared.constructs == ()


def test_inherited_member_keeps_predecessor_source_default(tmp_path: Path) -> None:
    revision = _successor(
        tmp_path,
        'formula_source_refs = ["successor-source"]\n',
    )

    inherited = next(item for item in revision.formulas if item.id == _CUOTA_FORMULA)
    assert tuple(str(item) for item in inherited.source_refs) == ("aeat-manual",)
