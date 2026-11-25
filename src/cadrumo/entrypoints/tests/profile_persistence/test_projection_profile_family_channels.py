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
_COHABITATION_FACT = "renta_family.convive_con_otro_progenitor"


def _observed(result: ModeloProjectServiceResult, casilla_id: str) -> Decimal | None:
    rows = [row.value for row in result.casilla_observations if row.casilla_id == casilla_id]
    return rows[0] if rows else None


@pytest.mark.parametrize(
    ("situation", "lives_with_other_parent", "expected"),
    [
        ("casado", None, Decimal("3400.00")),
        ("soltero", False, Decimal("2150.00")),
        ("soltero", True, Decimal("0.00")),
    ],
)
def test_the_family_situation_selects_the_joint_filing_reduction(
    tmp_path: Path,
    situation: str,
    lives_with_other_parent: bool | None,
    expected: Decimal,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """Art. 84.2 LIRPF: 3.400 EUR for spouses, 2.150 EUR for a single parent, none while living with the other parent."""
    cohabitation = (
        ()
        if lives_with_other_parent is None
        else (UserProfileFact(path=_COHABITATION_FACT, value=lives_with_other_parent),)
    )
    result = run_projection(
        tmp_path,
        operation,
        profile_facts=(
            *_JOINT,
            UserProfileFact(path="renta_family.situacion_familiar", value=situation),
            *cohabitation,
        ),
    )

    assert _observed(result, _REDUCTION_CASILLA) == expected


def test_a_single_parent_who_has_not_said_whether_they_live_with_the_other_parent_is_given_no_reduction(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """An undeclared fact is neither false nor zero: no 2.150 EUR reduction is invented for it.

    The reduction feeds the base liquidable, which the projection result requires,
    so the projection refuses and names the fact it could not read.
    """
    with pytest.raises(ModeloProjectionError) as refused:
        run_projection(
            tmp_path,
            operation,
            profile_facts=(*_JOINT, UserProfileFact(path="renta_family.situacion_familiar", value="soltero")),
        )

    context = refused.value.context
    assert context is not None
    assert context["casilla_produced"] is False
    assert context["profile_facts"] == _COHABITATION_FACT, context
    assert "command" not in context
    assert refused.value.translated_message == "application.modelo.projection_words.profile_fact_missing"
    rendered = tr(refused.value.translated_message, **context)
    assert _COHABITATION_FACT in rendered
    assert "aeat" not in rendered.lower() and "`" not in rendered


def test_an_individual_filing_without_the_fact_needs_no_family_reduction(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The reduction formula never reads the fact on an individual filing, so the box is a true zero."""
    result = run_projection(tmp_path, operation)

    assert _observed(result, _REDUCTION_CASILLA) == Decimal("0.00")
