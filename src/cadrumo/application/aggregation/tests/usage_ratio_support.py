"""Usage-ratio fixtures for aggregation tests: no stored override, and a declared dwelling.

The dwelling profile declares what ``config profile edit`` writes -- 20 m2 of office in
a 100 m2 home -- and the helpers read the statutory home-office share back out of the
real resolvers the production paths use, so a test states its expected figure by hand
and cannot inherit it from the code under test.
"""

from __future__ import annotations

from decimal import Decimal

from cadrumo.domain.calculations.registry.tests.published_authority import (
    leased_profile_create_context as _profile_creation_context_for_test,
)
from cadrumo.domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.categories.spending_category import SpendingCategory
from ....domain.usage_ratios.model import UsageRatioProfile
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ...ledger.ratios import resolve_business_share_pct
from ...user_profile.censo_sync import raw_afectacion_ratio_for_record
from ...user_profile.usage_ratio_resolution import resolve_effective_usage_ratios

#: What the dwelling profile's 20 / 100 m2 and the 30 per cent of LIRPF art. 30.2.5.b make of a
#: home-office suministro: 0.20 * 0.30. Written out here, not read from a resolver.
HOME_OFFICE_SUMINISTRO_RATIO = Decimal("0.06")

#: The degree of use the dwelling profile gives a home-office row: 20 / 100, with no
#: statutory factor. It is the row's ``business_pct`` and what IVA deducts.
HOME_OFFICE_DEGREE_OF_USE = Decimal("0.20")

_FILING_YEAR = 2025


def no_stored_usage_ratios(*, bucket_id: str, operation: PinnedAuthorityOperation) -> UsageRatioProfile:
    """Return the profile of a bucket whose operator never ran ``ratios set``."""
    del bucket_id, operation
    return UsageRatioProfile()


def dwelling_profile(*, office_m2: Decimal = Decimal("20")) -> UserProfileRecord:
    """Return a profile declaring an ``office_m2`` office (20 m2 by default) in a 100 m2 dwelling."""
    return _create_profile_record_for_test(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id="22222222-2222-4222-8222-222222222222",
        facts=(
            UserProfileFact(path="vivienda_office.office_m2", value=office_m2),
            UserProfileFact(path="vivienda_office.total_m2", value=Decimal("100")),
        ),
        context=_profile_creation_context_for_test(),
    )


def dwelling_usage_ratios(
    profile: UserProfileRecord,
    *,
    bucket_id: str,
    operation: PinnedAuthorityOperation,
) -> dict[SpendingCategory, Decimal]:
    """Return the effective per-category ratios the calculation paths resolve for ``profile``."""
    return resolve_effective_usage_ratios(
        bucket_id=bucket_id,
        year=_FILING_YEAR,
        usage_ratio_profile_loader=no_stored_usage_ratios,
        operation=operation,
        profile_record=profile,
    )


def dwelling_classify_share(
    profile: UserProfileRecord,
    category: SpendingCategory,
    *,
    operation: PinnedAuthorityOperation,
) -> Decimal | None:
    """Return the ``business_pct`` (degree of use) the classify path stamps on a row of ``category``."""
    return resolve_business_share_pct(
        operator_supplied=None,
        category=category,
        censo_afectacion_ratio=raw_afectacion_ratio_for_record(profile),
        year=_FILING_YEAR,
        operation=operation,
    ).business_pct


__all__ = [
    "HOME_OFFICE_DEGREE_OF_USE",
    "HOME_OFFICE_SUMINISTRO_RATIO",
    "dwelling_classify_share",
    "dwelling_profile",
    "dwelling_usage_ratios",
    "no_stored_usage_ratios",
]
