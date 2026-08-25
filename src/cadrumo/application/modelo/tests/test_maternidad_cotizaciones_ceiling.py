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

from ....core.external_constants import DEDUCCION_MATERNIDAD_COTIZACIONES_CEILING_RETIRED_FILING_YEAR
from ....core.resources import resources
from ....domain.contribuyente import DescendantInfo, descendant_facts_from_list
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from .._profile_binding import resolve_maternidad_meses

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "0de41ce4-0000-4000-8000-000000000626"
_T0 = datetime(2026, 8, 5, 10, 0, tzinfo=UTC)

#: The years the ceiling applied to. The Manual Practico fixes the cutover at
#: 1 January 2023, so 2023 is NOT a member -- a fix spanning four years would
#: swap this over-grant for an under-grant in the year the limitation ended.
_CEILINGED_YEARS = (2020, 2021, 2022)

#: The first year the deduccion is correctly un-capped.
_FIRST_UNCEILINGED_YEAR = 2023


def _record_declaring_months(filing_year: int) -> UserProfileRecord:
    """A profile with one clearly-eligible descendant declaring a full year of months."""
    child = DescendantInfo(birth_date=date(filing_year - 1, 6, 1), meses_madre_trabajo=tuple(range(1, 13)))
    return UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET,
        facts=tuple(UserProfileFact(path=p, value=v) for p, v in descendant_facts_from_list((child,))),
        created_at=_T0,
        updated_at=_T0,
    )


def _resolution(filing_year: int):
    snapshot = resources().modelos.authority.snapshot("100", filing_year=filing_year, period="0A")
    return resolve_maternidad_meses(_record_declaring_months(filing_year), snapshot)


class TestCotizacionesCeilingYears:
    """A descendant the engine would otherwise grant must yield nothing before 2023."""

    def test_no_deduccion_is_granted_while_the_ceiling_applied(self) -> None:
        """The over-grant this test closes, one assertion per affected year.

        The descendant is eligible on every other axis, so a granted figure here
        would be un-capped by the cotizaciones the statute required.
        """
        for filing_year in _CEILINGED_YEARS:
            resolution = _resolution(filing_year)
            assert resolution.pairs == (), filing_year

    def test_the_withholding_is_disclosed_rather_than_silent(self) -> None:
        """A declared figure that vanishes without explanation is the other failure.

        The operator typed months and receives nothing; the flag that drives the
        advisory must be set so the calculate path can say why.
        """
        for filing_year in _CEILINGED_YEARS:
            resolution = _resolution(filing_year)
            assert resolution.cotizaciones_ceiling_inexpressible is True, filing_year
            assert resolution.declares_meses is True, filing_year

    def test_the_year_the_limitation_ended_is_granted_in_full(self) -> None:
        """2023 is the boundary and is NOT affected.

        Including it would trade this over-grant for an under-grant in the first
        year the deduccion was correctly un-capped -- the same year-scoping error
        arriving from the opposite direction.
        """
        resolution = _resolution(_FIRST_UNCEILINGED_YEAR)

        assert resolution.pairs == (("0", 12),)
        assert resolution.cotizaciones_ceiling_inexpressible is False

    def test_the_boundary_constant_matches_the_manual(self) -> None:
        """The cutover is a regulatory date, so it is pinned rather than implied.

        Anti-tautology over the gate: the constant and the affected set are
        asserted against each other, so moving one without the other fails.
        """
        assert DEDUCCION_MATERNIDAD_COTIZACIONES_CEILING_RETIRED_FILING_YEAR == _FIRST_UNCEILINGED_YEAR
        assert max(_CEILINGED_YEARS) == _FIRST_UNCEILINGED_YEAR - 1
