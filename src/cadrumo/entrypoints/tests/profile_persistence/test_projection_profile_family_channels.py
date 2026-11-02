"""The Modelo 100 projection carries a profile family fact on the profile's channel only."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.application.modelo.projection import ModeloProjectionError, ModeloProjectServiceResult
from cadrumo.core.i18n.render import tr
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.user_profile.values import UserProfileFact

from .projection_m130_seeding_support import run_projection

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_JOINT = (
    UserProfileFact(path="renta_filing.declaration_type", value="2"),
    UserProfileFact(path="renta_spouse.tax_id", value="00000000T"),
)
_REDUCTION_CASILLA = "0461"


def _observed(result: ModeloProjectServiceResult, casilla_id: str) -> Decimal | None:
    rows = [row.value for row in result.casilla_observations if row.casilla_id == casilla_id]
    return rows[0] if rows else None


@pytest.mark.parametrize(
    ("minor_children", "expected"),
    [(False, Decimal("3400.00")), (True, Decimal("2150.00"))],
)
def test_declared_minor_children_select_the_joint_filing_reduction(
    tmp_path: Path, minor_children: bool, expected: Decimal, *, operation: PinnedAuthorityOperation
) -> None:
    """Art. 84 LIRPF: 3.400 EUR joint without minors, 2.150 EUR single-parent unit with minors."""
    result = run_projection(
        tmp_path,
        operation,
        profile_facts=(*_JOINT, UserProfileFact(path="renta_family.minor_children_in_unit", value=minor_children)),
    )

    assert _observed(result, _REDUCTION_CASILLA) == expected


def test_a_joint_filing_without_the_minor_children_fact_is_not_given_a_stand_in_reduction(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """An undeclared fact is neither false nor zero: no 3.400 EUR reduction is invented for it.

    The reduction feeds the base liquidable, which the projection result requires,
    so the projection refuses and names the box it could not produce.
    """
    with pytest.raises(ModeloProjectionError) as refused:
        run_projection(tmp_path, operation, profile_facts=_JOINT)

    context = refused.value.context
    assert context is not None
    assert context["casilla_produced"] is False
    assert context["profile_facts"] == "renta_family.minor_children_in_unit", context
    assert context["command"] == "aeat config profile edit"
    assert refused.value.translated_message == "cli.app.modelo.project.profile_fact_missing"
    rendered = tr(refused.value.translated_message, **context)
    assert "renta_family.minor_children_in_unit" in rendered
    assert "aeat config profile edit" in rendered


def test_an_individual_filing_without_the_fact_needs_no_family_reduction(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The reduction formula never reads the fact on an individual filing, so the box is a true zero."""
    result = run_projection(tmp_path, operation)

    assert _observed(result, _REDUCTION_CASILLA) == Decimal("0.00")
