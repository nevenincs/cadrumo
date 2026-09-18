"""Focused contract tests for keyed-family field, member, clear, and order deltas."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.keyed_families import family_spec
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from ..compiler.loader import inherit_keyed_family, load_modelo_directory
from ..compiler.loader_materialisation import patch_family_sequences
from .test_restated_family_merge import (
    _BASE_FORMULA,
    _CUOTA_FORMULA,
    _RECARGO_FORMULA,
    _SUCCESSOR,
    _build_modelo,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: A clearance names its cause and the reason somebody wrote, so an emptied family
#: records why it is empty rather than going empty on a bare family name.
_CLEARED_CONSTRUCTS = (
    'cleared_families = [{ family = "constructs", cause = "official_structure_withdraws", '
    'reason = "The document governing this edition lays out no construct, so the earlier one is withdrawn." }]\n'
)


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
    modelo = _build_modelo(
        tmp_path / "cleared",
        successor_extra=_CLEARED_CONSTRUCTS,
    )
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


@pytest.mark.parametrize(
    ("selector", "storage_only", "expected"),
    [
        ({"years": [2024], "periods": ["0A"]}, False, 1),
        ({"year_from": 2023, "year_to": 2025, "periods": ["0A"]}, False, 1),
        ({"years": [2025], "periods": ["0A"]}, False, 0),
        ({"years": [2025], "periods": ["0A"]}, True, 1),
    ],
    ids=("matching", "overlapping", "nonmatching", "storage-reconstruction"),
)
def test_deadline_storage_reconstruction_is_separate_from_period_eligibility(
    selector: dict[str, object], storage_only: bool, expected: int
) -> None:
    spec = family_spec("deadline_windows")
    assert spec is not None
    assert spec.identity is not None
    member = {"id": "deadline-2024", "filing_year": 2024, "period": "2024 0A"}

    result = inherit_keyed_family(
        "deadline fixture",
        revision_id="2025",
        predecessor_id="2024",
        predecessor={"deadline_windows": (member,)},
        storage_only=storage_only,
        section=spec.section,
        identity=spec.identity,
        identity_fields=spec.identity_fields,
        casilla_identity_fields=spec.casilla_identity_fields,
        period_scoped=spec.period_scoped,
        inherited=(member,),
        inherited_casillas=(),
        successor_casillas=(),
        successor={"period_selector": selector, "deadline_windows": ()},
    )

    assert len(result) == expected


def test_sequence_delta_reuses_members_and_restores_exact_order() -> None:
    result = patch_family_sequences(
        "sequence fixture",
        {"claim": {"refs": ("a", "b", "c")}},
        {"claim.refs": ("d",)},
        {"claim.refs": (1,)},
        {"claim.refs": (2, 0, 1)},
    )

    assert result == {"claim": {"refs": ("d", "a", "c")}}
