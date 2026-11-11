"""The pre-2023 cotizaciones ceiling: withheld because it cannot be applied.

Until 2022 Art. 81.1 LIRPF capped the deduccion por maternidad at the mother's
"cotizaciones y cuotas totales a la Seguridad Social y mutualidades devengadas en
cada periodo impositivo" -- stated in the Manual Practico de Renta 2020 and 2022.
The Manual Practico de Renta 2024 records its removal in terms: "desaparece esta
limitacion del importe de la deduccion a las cotizaciones devengadas en el periodo
impositivo … el nuevo regimen resulta aplicable desde el 1 de enero de 2023".

This application cannot apply that cap for the affected years. The cotizaciones
registry binding exists only in the 2024 revision and the profile fact is
2024-pinned (`cotizaciones_ss_madre_2024`), so no figure is reachable for 2020,
2021 or 2022. Computing anyway grants an un-capped deduccion, which over-grants
and therefore under-declares.

WHAT THESE TESTS ASSERT, AND WHY IT IS PHRASED THIS WAY. They assert THE CEILING
-- that a pre-2023 filing year yields no deduccion and says so -- rather than
asserting that this change introduced no un-ceilinged path. The un-ceilinged
arithmetic PREDATES this change: the retired calculate-time flag computed
`sum(min(meses x 100, 1200))` with no cotizaciones term at all, and what
changed was the population reaching it, from operators who typed the flag
to every operator with declared months. A guard phrased as "we introduce no
un-ceilinged path" would therefore be satisfiable BY the defect it is meant to
catch, which is the failure mode this file exists to avoid.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError
from cadrumo.domain.user_profile.values import create_user_profile_record

from ....domain.calculations.registry.tests.authored_editions import manual_edition_matches, manual_editions_printing
from ....domain.calculations.registry.tests.published_authority import (
    PublishedGovernedFactSource,
    leased_profile_create_context,
    published_snapshot,
    published_supported_filing_years,
)
from ....domain.contribuyente.descendant import DescendantInfo
from ....domain.contribuyente.descendant_facts import descendant_facts_from_list
from ....domain.contribuyente.family_fact_context import FamilyFactResolutionContext
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ..profile_maternidad_meses import resolve_maternidad_meses

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_BUCKET = "0de41ce4-0000-4000-8000-000000000626"
_T0 = datetime(1980, 8, 5, 10, 0, tzinfo=UTC)


def _manual_cutover_year() -> int:
    """The year the Manual Practico de Renta says the un-capped regime applies from."""
    matches = manual_edition_matches("renta", r"nuevo regimen resulta aplicable desde el 1 de enero de (\d{4})")
    cutovers = {int(match.group(1)) for match in matches.values()}
    assert len(cutovers) == 1, "the manual editions disagree on the year the limitation ended"
    return cutovers.pop()


#: The first year the deduccion is correctly un-capped, as the manual states it.
_FIRST_UNCEILINGED_YEAR = _manual_cutover_year()

#: The editions of the manual that still print the cap, and so the first year it applied to.
_CEILING_MANUAL_EDITIONS = manual_editions_printing(
    "renta",
    "cotizaciones y cuotas totales a la seguridad social y mutualidades devengadas en cada periodo impositivo",
)
_FIRST_KNOWN_CEILINGED_YEAR = min(_CEILING_MANUAL_EDITIONS)


def _supported_filing_years() -> tuple[int, ...]:
    supported_years = published_supported_filing_years()
    assert supported_years is not None, "the bundled registry declares no supported filing years"
    return supported_years.years


#: The supported years the ceiling applied to. The Manual Practico fixes the
#: cutover at 1 January 2023, so 2023 is NOT a member -- a fix spanning one more
#: year would swap this over-grant for an under-grant in the year the limitation
#: ended. Ceilinged years below the supported floor are refused outright.
_CEILINGED_YEARS = tuple(year for year in _supported_filing_years() if year < _FIRST_UNCEILINGED_YEAR)
_UNSUPPORTED_CEILINGED_YEARS = tuple(
    year for year in range(_FIRST_KNOWN_CEILINGED_YEAR, _FIRST_UNCEILINGED_YEAR) if year not in _CEILINGED_YEARS
)


def _record_declaring_months(filing_year: int) -> UserProfileRecord:
    """A profile with one clearly-eligible descendant declaring a full year of months."""
    child = DescendantInfo(birth_date=date(filing_year - 1, 6, 1), meses_madre_trabajo=tuple(range(1, 13)))
    return create_user_profile_record(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET,
        facts=tuple(UserProfileFact(path=p, value=v) for p, v in descendant_facts_from_list((child,))),
        created_at=_T0,
        updated_at=_T0,
        context=leased_profile_create_context(),
    )


def _resolution(filing_year: int, *, operation: PinnedAuthorityOperation):
    snapshot = published_snapshot("100", filing_year=filing_year, period="0A")
    return resolve_maternidad_meses(_record_declaring_months(filing_year), snapshot, operation=operation)


def _retired_ceiling_year() -> int:
    coordinate = date(_FIRST_UNCEILINGED_YEAR, 12, 31)
    return FamilyFactResolutionContext(
        authority=PublishedGovernedFactSource(),
        filing_period=coordinate,
        devengo_date=coordinate,
    ).integer("lirpf-art-81-contribution-ceiling-retired-effective-year")


class TestCotizacionesCeilingYears:
    """A descendant the engine would otherwise grant must yield nothing before 2023."""

    def test_no_deduccion_is_granted_while_the_ceiling_applied(self, *, operation: PinnedAuthorityOperation) -> None:
        """The over-grant this test closes, one assertion per affected year.

        The descendant is eligible on every other axis, so a granted figure here
        would be un-capped by the cotizaciones the statute required.
        """
        assert _CEILINGED_YEARS, "no supported filing year falls under the ceiling"
        for filing_year in _CEILINGED_YEARS:
            resolution = _resolution(filing_year, operation=operation)
            assert resolution.pairs == (), filing_year

    def test_ceilinged_years_below_the_supported_floor_are_refused(
        self, *, operation: PinnedAuthorityOperation
    ) -> None:
        """A ceilinged year the product does not support is refused, never granted."""
        for filing_year in _UNSUPPORTED_CEILINGED_YEARS:
            with pytest.raises(FilingYearOutsideSupportEnvelopeError):
                _resolution(filing_year, operation=operation)

    def test_the_withholding_is_disclosed_rather_than_silent(self, *, operation: PinnedAuthorityOperation) -> None:
        """A declared figure that vanishes without explanation is the other failure.

        The operator typed months and receives nothing; the flag that drives the
        advisory must be set so the calculate path can say why.
        """
        for filing_year in _CEILINGED_YEARS:
            resolution = _resolution(filing_year, operation=operation)
            assert resolution.cotizaciones_ceiling_inexpressible is True, filing_year
            assert resolution.declares_meses is True, filing_year

    def test_the_year_the_limitation_ended_is_granted_in_full(self, *, operation: PinnedAuthorityOperation) -> None:
        """2023 is the boundary and is NOT affected.

        Including it would trade this over-grant for an under-grant in the first
        year the deduccion was correctly un-capped -- the same year-scoping error
        arriving from the opposite direction.
        """
        resolution = _resolution(_FIRST_UNCEILINGED_YEAR, operation=operation)

        assert resolution.pairs == (("0", 12),)
        assert resolution.cotizaciones_ceiling_inexpressible is False

    def test_the_boundary_constant_matches_the_manual(self) -> None:
        """The cutover is a regulatory date, so it is pinned rather than implied.

        Anti-tautology over the gate: the constant and the affected set are
        asserted against each other, so moving one without the other fails.
        """
        assert _retired_ceiling_year() == _FIRST_UNCEILINGED_YEAR
        assert max(_CEILING_MANUAL_EDITIONS) == _FIRST_UNCEILINGED_YEAR - 1
        assert max(_CEILINGED_YEARS) == _FIRST_UNCEILINGED_YEAR - 1
