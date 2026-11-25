"""Where a pension contribution record lands in each Modelo 100 edition, read from the published registry.

The expected casillas are the textual matches the Modelo 345 subclave wording and
the Modelo 100 dictionary wording make, written here as an independent oracle;
the registry rows must agree with it in every edition that places claves. Every
year comes from the published support envelope, never from a literal.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from functools import cache

import pytest
from pydantic import ValidationError

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.prevision_social import (
    PrevisionSocialBeneficiario,
    PrevisionSocialClave,
    PrevisionSocialPlacementRefusal,
    PrevisionSocialSubclave,
)
from ...calculations.registry.authority import bundled_indexed_authority
from ...calculations.registry.schema import ModeloRevision
from ..prevision_social_contribution import PrevisionSocialContribution
from ..prevision_social_contribution_placement import (
    ContributionPlacement,
    ContributionPlacementRefused,
    place_contribution,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_C = PrevisionSocialClave
_S = PrevisionSocialSubclave
_R = PrevisionSocialPlacementRefusal

_PLACED: dict[tuple[PrevisionSocialClave, PrevisionSocialSubclave | None, bool | None], str] = {
    (_C.CLAVE_A, _S.SUBCLAVE_01, None): "0465",
    (_C.CLAVE_A, _S.SUBCLAVE_02, None): "0426",
    (_C.CLAVE_C, _S.SUBCLAVE_01, None): "0427",
    (_C.CLAVE_C, _S.SUBCLAVE_02, None): "0499",
    (_C.CLAVE_C, _S.SUBCLAVE_03, None): "0438",
    (_C.CLAVE_E, _S.SUBCLAVE_01, None): "0499",
    (_C.CLAVE_F, _S.SUBCLAVE_01, None): "0465",
    (_C.CLAVE_F, _S.SUBCLAVE_02, None): "0426",
    (_C.CLAVE_G, _S.SUBCLAVE_01, None): "0427",
    (_C.CLAVE_G, _S.SUBCLAVE_02, None): "0438",
    (_C.CLAVE_J, _S.SUBCLAVE_01, False): "0465",
    (_C.CLAVE_J, _S.SUBCLAVE_01, True): "0426",
    (_C.CLAVE_J, _S.SUBCLAVE_02, None): "0438",
    (_C.CLAVE_J, _S.SUBCLAVE_03, None): "0427",
    (_C.CLAVE_J, _S.SUBCLAVE_04, None): "0499",
    (_C.CLAVE_L, _S.SUBCLAVE_01, None): "0466",
    (_C.CLAVE_L, _S.SUBCLAVE_02, None): "0499",
}
"""Pairs the subclave and casilla texts of every placing edition match."""

_AUTONOMOS_SIMPLIFIED_PLAN = (_C.CLAVE_A, _S.SUBCLAVE_03, None)
"""Defined from the ejercicio after the first placing design; reaches 0499 where defined."""

_INDIRECT = ((_C.CLAVE_B, None), (_C.CLAVE_H, None), (_C.CLAVE_K, None))
_UNPLACED = (
    (_C.CLAVE_C, _S.SUBCLAVE_04),
    (_C.CLAVE_D, _S.SUBCLAVE_01),
    (_C.CLAVE_D, _S.SUBCLAVE_02),
    (_C.CLAVE_D, _S.SUBCLAVE_03),
    (_C.CLAVE_E, _S.SUBCLAVE_02),
    (_C.CLAVE_I, _S.SUBCLAVE_01),
    (_C.CLAVE_I, _S.SUBCLAVE_02),
    (_C.CLAVE_L, _S.SUBCLAVE_03),
)


@cache
def _revisions_by_year() -> tuple[tuple[int, ModeloRevision], ...]:
    """Return the revision the Modelo 100 of every supported year is calculated against, oldest first."""
    with bundled_indexed_authority().operation() as operation:
        years = sorted(operation.supported_filing_years().years)
        return tuple(
            (
                year,
                operation.snapshot(
                    "100", filing_year=year, period="0A", grade=RegistryAuthorityGrade.CALCULATION
                ).revision,
            )
            for year in years
        )


def _placing() -> tuple[tuple[int, ModeloRevision], ...]:
    return tuple((year, revision) for year, revision in _revisions_by_year() if revision.prevision_social_placements)


def _record(
    year: int,
    clave: PrevisionSocialClave,
    subclave: PrevisionSocialSubclave | None,
    *,
    same_plan: bool | None = None,
    beneficiary: PrevisionSocialBeneficiario = PrevisionSocialBeneficiario.TAXPAYER,
) -> PrevisionSocialContribution:
    return PrevisionSocialContribution(
        ejercicio=year,
        issuer_tax_id="V00010080",
        issuer_legal_name="Gestora Sintetica SA",
        issuer_ref="a" * 64,
        plan_tax_id="V00010090",
        plan_name="Plan Sintetico",
        plan_ref="c" * 64,
        clave=clave,
        subclave=subclave,
        amount=Decimal("1500.00"),
        beneficiary=beneficiary,
        employer_contributed_to_same_plan=same_plan,
        evidence_fingerprint="b" * 64,
        captured_at=datetime(year + 1, 3, 1, tzinfo=UTC),
    )


def test_every_supported_year_is_calculated_against_a_placing_edition() -> None:
    """Every year the envelope admits has a bundled Modelo 345 design behind its edition."""
    assert _revisions_by_year()
    assert _placing() == _revisions_by_year()


def test_every_admitted_pair_reaches_its_casilla_in_every_placing_edition() -> None:
    for year, revision in _placing():
        for (clave, subclave, same_plan), casilla in _PLACED.items():
            placed = place_contribution(revision, _record(year, clave, subclave, same_plan=same_plan))
            assert isinstance(placed, ContributionPlacement), (year, clave, subclave, same_plan, placed)
            assert str(placed.casilla_id) == casilla, (year, clave, subclave, same_plan)


def test_the_autonomos_simplified_plan_subclave_is_placed_only_where_its_design_defines_it() -> None:
    (first_year, first), *later = _placing()
    clave, subclave, _ = _AUTONOMOS_SIMPLIFIED_PLAN
    assert place_contribution(first, _record(first_year, clave, subclave)) == ContributionPlacementRefused(
        reason=_R.UNPLACED_CLAVE
    )
    assert later
    for year, revision in later:
        placed = place_contribution(revision, _record(year, clave, subclave))
        assert placed == ContributionPlacement(casilla_id="0499", placement_id="a-03"), year


@pytest.mark.parametrize(("clave", "subclave"), _INDIRECT)
def test_an_indirect_match_is_refused(clave: PrevisionSocialClave, subclave: PrevisionSocialSubclave | None) -> None:
    for year, revision in _placing():
        assert place_contribution(revision, _record(year, clave, subclave)) == ContributionPlacementRefused(
            reason=_R.INDIRECT_MATCH
        ), year


def test_the_pepp_clave_is_unplaced_before_its_design_and_indirect_after() -> None:
    (first_year, first), *later = _placing()
    assert place_contribution(first, _record(first_year, _C.CLAVE_M, None)) == ContributionPlacementRefused(
        reason=_R.UNPLACED_CLAVE
    )
    for year, revision in later:
        assert place_contribution(revision, _record(year, _C.CLAVE_M, None)) == ContributionPlacementRefused(
            reason=_R.INDIRECT_MATCH
        ), year


@pytest.mark.parametrize(("clave", "subclave"), _UNPLACED)
def test_a_pair_no_text_places_is_refused(clave: PrevisionSocialClave, subclave: PrevisionSocialSubclave) -> None:
    for year, revision in _placing():
        assert place_contribution(revision, _record(year, clave, subclave)) == ContributionPlacementRefused(
            reason=_R.UNPLACED_CLAVE
        ), year


def test_the_same_plan_subclave_is_refused_when_the_answer_is_unstated() -> None:
    for year, revision in _placing():
        record = _record(year, _C.CLAVE_J, _S.SUBCLAVE_01)
        assert place_contribution(revision, record) == ContributionPlacementRefused(
            reason=_R.SAME_PLAN_SPLIT_UNSTATED
        ), year


def test_an_unsplit_pair_ignores_a_stated_same_plan_answer() -> None:
    for year, revision in _placing():
        placed = place_contribution(revision, _record(year, _C.CLAVE_A, _S.SUBCLAVE_01, same_plan=True))
        assert placed == ContributionPlacement(casilla_id="0465", placement_id="a-01"), year


def test_every_clave_is_refused_by_an_edition_that_places_none() -> None:
    """An edition declaring no placement has no Modelo 345 design behind it, so nothing is placed by analogy."""
    year, revision = _revisions_by_year()[-1]
    bare = revision.model_copy(update={"prevision_social_placements": ()})
    for clave, subclave, same_plan in _PLACED:
        assert place_contribution(bare, _record(year, clave, subclave, same_plan=same_plan)) == (
            ContributionPlacementRefused(reason=_R.DESIGN_NOT_BUNDLED)
        ), (clave, subclave)


@pytest.mark.parametrize(
    "beneficiary", [PrevisionSocialBeneficiario.SPOUSE, PrevisionSocialBeneficiario.DISABLED_PERSON]
)
def test_a_contribution_to_another_persons_system_is_refused(beneficiary: PrevisionSocialBeneficiario) -> None:
    for year, revision in _revisions_by_year():
        record = _record(year, _C.CLAVE_A, _S.SUBCLAVE_01, beneficiary=beneficiary)
        assert place_contribution(revision, record) == ContributionPlacementRefused(
            reason=_R.BENEFICIARY_OUT_OF_SCOPE
        ), year


def test_a_subclave_the_design_does_not_define_is_refused_at_record_time() -> None:
    year, _ = _revisions_by_year()[-1]
    with pytest.raises(ValidationError, match="defines no such subclave"):
        _record(year, _C.CLAVE_B, _S.SUBCLAVE_01)
    with pytest.raises(ValidationError, match="defines no such subclave"):
        _record(year, _C.CLAVE_A, None)


def test_a_negative_or_third_decimal_amount_is_refused() -> None:
    year, _ = _revisions_by_year()[-1]
    record = _record(year, _C.CLAVE_A, _S.SUBCLAVE_01)
    for amount in (Decimal("-1.00"), Decimal("1.001")):
        with pytest.raises(ValidationError):
            PrevisionSocialContribution.model_validate({**record.model_dump(), "amount": amount})


def test_a_plan_reference_without_the_plans_tax_id_is_refused() -> None:
    year, _ = _revisions_by_year()[-1]
    record = _record(year, _C.CLAVE_A, _S.SUBCLAVE_01)
    with pytest.raises(ValidationError, match="plan reference"):
        PrevisionSocialContribution.model_validate({**record.model_dump(), "plan_tax_id": None})
