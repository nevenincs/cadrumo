"""The censo-declared dwelling area reaches the deduction without being retyped.

LIRPF art. 30.2.5.b makes the deductible share of a suministro the statutory thirty
per cent applied to "la proporción existente entre los metros cuadrados de la vivienda
destinados a la actividad respecto a su superficie total". The taxpayer declares those
m² as censo 036 facts, and until this module existed nothing carried the declaration
into the calculation: the ratio had to be typed a second time through
``aeat app ledger ratios set``, and a filer who declared their m² and never did that
deducted nothing at all on utilities.

Deriving is not new policy. The censo guard already refuses any stored home-office
ratio that is not exactly the censo-derived one, so filling an absent one produces the
number the guard would have insisted on anyway.

No mocks: real profile records through the real repository, the real registry rules and
the real derivation.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....adapters.persistence.tests.runtime_profile_fixture import (
    bucket_scoped_runtime_profile_fixture,
)
from ....domain.categories.spending_category import SpendingCategory
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ..usage_ratio_resolution import resolve_effective_usage_ratios

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "61616161-6161-4161-8161-616161616161"
_YEAR = 2025

_runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID)


def _store_profile(**facts: str) -> None:
    """Persist a real encrypted profile record carrying the censo facts.

    Mirrors what ``config profile edit`` writes, through the same capsule seeder
    the preflight tests use, so the resolver reads facts of the shape production
    actually stores.
    """
    seed_test_profile_record(
        UserProfileRecord(
            profile_id=_BUCKET_ID,
            setup_state=ProfileSetupState.COMPLETE,
            facts=tuple(
                UserProfileFact(path=path, value=Decimal(value) if path.startswith("vivienda_office.") else value)
                for path, value in facts.items()
            ),
        ),
    )


def test_a_declared_dwelling_area_produces_the_suministros_ratio(_runtime_profile: object) -> None:
    """DISCRIMINATING. The gap this module closes.

    20 m² of 100 m² is a 0.20 proportion, so art. 30.2.5.b gives 0.30 × 0.20 = 0.06
    of the utility bill. Before this resolver the same profile produced no ratio at
    all and the deduction was zero.
    """
    _store_profile(
        **{"vivienda_office.office_m2": "20", "vivienda_office.total_m2": "100"},
    )

    ratios = resolve_effective_usage_ratios(bucket_id=_BUCKET_ID, year=_YEAR)

    assert ratios[SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ] == Decimal("0.060")


def test_the_ownership_costs_take_the_raw_proportion(_runtime_profile: object) -> None:
    """SUPPORTING. The two home-office families differ, and both are derived.

    The ownership costs are grounded on the general art. 29.2 partial-affectation
    doctrine, which carries no thirty-per-cent factor, so they take the area
    proportion itself. Asserting both keeps the statutory factor from being applied
    where no provision establishes it.
    """
    _store_profile(
        **{"vivienda_office.office_m2": "20", "vivienda_office.total_m2": "100"},
    )

    ratios = resolve_effective_usage_ratios(bucket_id=_BUCKET_ID, year=_YEAR)

    assert ratios[SpendingCategory.AMORTIZACION_VIVIENDA_AFECTO] == Decimal("0.20")


def test_no_declared_area_resolves_to_nothing_rather_than_a_guess(_runtime_profile: object) -> None:
    """DISCRIMINATING, and the half that keeps the retired defect retired.

    A profile with no dwelling m² supplies no second factor, and none may be
    invented. The categories stay ineligible, which is the honest outcome: the
    registry cannot know how much of a home is an office.
    """
    _store_profile(**{"identity.tax_id": "X1234567L"})

    ratios = resolve_effective_usage_ratios(bucket_id=_BUCKET_ID, year=_YEAR)

    assert SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ not in ratios


def test_an_absent_profile_resolves_to_nothing(_runtime_profile: object) -> None:
    """SUPPORTING. A bucket with no profile must not raise on the calculate path."""
    assert resolve_effective_usage_ratios(bucket_id=_BUCKET_ID, year=_YEAR) == {}
