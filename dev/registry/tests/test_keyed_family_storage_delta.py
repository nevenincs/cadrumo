"""Focused contract tests for keyed-family field, member, clear, and order deltas."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.keyed_families import family_spec
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ..compiler.keyed_family_inheritance import inherit_keyed_family
from ..compiler.keyed_family_storage_delta import patch_family_sequences
from ..compiler.loader import load_modelo_directory
from .synthetic_delta_edition_support import PREDECESSOR_EDITION, SUCCESSOR_EDITION
from .test_restated_family_merge import (
    BASE_FORMULA,
    CUOTA_FORMULA,
    RECARGO_FORMULA,
    build_modelo,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: A clearance names its cause and the reason somebody wrote, so an emptied family
#: records why it is empty rather than going empty on a bare family name.
_CLEARED_CONSTRUCTS = (
    'cleared_families = [{ family = "constructs", cause = "official_structure_withdraws", '
    'reason = "The document governing this edition lays out no construct, so the earlier one is withdrawn." }]\n'
)


def _successor(root: Path, declaration: str) -> ModeloRevision:
    return load_modelo_directory(build_modelo(root, successor_extra=declaration)).revisions[SUCCESSOR_EDITION]


def test_changed_member_authors_only_its_changed_nested_field(tmp_path: Path) -> None:
    revision = _successor(
        tmp_path,
        f'[[revisions."{SUCCESSOR_EDITION}".family_overrides]]\n'
        'family = "formulas"\n'
        f'selector = {{ revision = "{PREDECESSOR_EDITION}", id = "modelo-999-cuota" }}\n'
        'fields = { expression = { literal = "7" } }\n',
    )

    formula = next(item for item in revision.formulas if item.id == CUOTA_FORMULA)
    assert formula.expression.literal == 7
    assert str(formula.target_casilla_id) == "0002"


def test_member_removal_addition_and_order_are_exact(tmp_path: Path) -> None:
    revision = _successor(
        tmp_path,
        f'[[revisions."{SUCCESSOR_EDITION}".family_removals]]\n'
        'family = "formulas"\n'
        f'selector = {{ revision = "{PREDECESSOR_EDITION}", id = "modelo-999-cuota" }}\n'
        f'[[revisions."{SUCCESSOR_EDITION}".family_positions]]\n'
        'family = "formulas"\n'
        'id = "modelo-999-recargo"\n'
        "position = 0\n",
    )

    assert tuple(item.id for item in revision.formulas) == (RECARGO_FORMULA, BASE_FORMULA)


def test_explicit_clear_differs_from_omitted_family(tmp_path: Path) -> None:
    inherited = _successor(tmp_path / "inherited", "")
    modelo = build_modelo(
        tmp_path / "cleared",
        successor_extra=_CLEARED_CONSTRUCTS,
    )
    successor_construct = next((modelo / "revisions" / SUCCESSOR_EDITION / "constructs").glob("*.toml"))
    successor_construct.unlink()
    successor_construct.parent.rmdir()
    cleared = load_modelo_directory(modelo).revisions[SUCCESSOR_EDITION]

    assert len(inherited.constructs) == 2
    assert cleared.constructs == ()


def test_inherited_member_keeps_predecessor_source_default(tmp_path: Path) -> None:
    revision = _successor(
        tmp_path,
        'formula_source_refs = ["successor-source"]\n',
    )

    inherited = next(item for item in revision.formulas if item.id == CUOTA_FORMULA)
    assert tuple(str(item) for item in inherited.source_refs) == ("aeat-manual",)


@pytest.mark.parametrize(
    ("selector", "expected"),
    [
        ({"years": [int(PREDECESSOR_EDITION)], "periods": ["0A"]}, 1),
        ({"year_from": filing_year_envelope().floor, "year_to": filing_year_envelope().horizon, "periods": ["0A"]}, 1),
        ({"years": [int(SUCCESSOR_EDITION)], "periods": ["0A"]}, 0),
    ],
    ids=("matching", "overlapping", "nonmatching"),
)
def test_a_deadline_is_inherited_only_into_an_edition_filing_its_period(
    selector: dict[str, object], expected: int
) -> None:
    """One rule on every edge: a storage baseline reuses payload, never another period's deadline."""
    spec = family_spec("deadline_windows")
    assert spec is not None
    assert spec.identity is not None
    predecessor_year = int(PREDECESSOR_EDITION)
    member = {
        "id": f"deadline-{predecessor_year}",
        "filing_year": predecessor_year,
        "period": str(Period.from_year_and_code(predecessor_year, "0A")),
    }

    result = inherit_keyed_family(
        "deadline fixture",
        revision_id=SUCCESSOR_EDITION,
        predecessor_id=PREDECESSOR_EDITION,
        predecessor={"deadline_windows": (member,)},
        family=spec,
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
