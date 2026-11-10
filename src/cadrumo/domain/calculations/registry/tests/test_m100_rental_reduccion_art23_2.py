"""Modelo 100 Art. 23.2 housing-rental reduction calculation tests, on the edition that declares the tier."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

import pytest

from .....core.authority_grade import RegistryAuthorityGrade
from ..schema import RegistrySnapshot
from . import m100_rental_reduccion_art23_2_scenarios as scenarios

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]


@pytest.fixture(scope="module")
def m100_tier_edition_snapshot(registry_snapshot: Callable[..., RegistrySnapshot]) -> RegistrySnapshot:
    """A formula-runtime calculation claim, never a filing one."""
    return registry_snapshot(
        "100",
        scenarios.TIER_EDITION_EXERCISE,
        "0A",
        revision_id=scenarios.TIER_EDITION_ID,
        grade=RegistryAuthorityGrade.CALCULATION,
    )


def test_tier_binding_is_layout_and_law_grounded(m100_tier_edition_snapshot: RegistrySnapshot) -> None:
    scenarios.check_tier_binding_is_layout_and_law_grounded(m100_tier_edition_snapshot)


@pytest.mark.parametrize(
    ("tier", "expected"),
    (
        ("tier-50", Decimal("5000.00")),
        ("tier-60", Decimal("6000.00")),
        ("tier-70", Decimal("7000.00")),
        ("tier-90", Decimal("9000.00")),
    ),
)
def test_0150_uses_operator_selected_art23_2_tier(
    m100_tier_edition_snapshot: RegistrySnapshot, tier: str, expected: Decimal
) -> None:
    scenarios.check_0150_uses_operator_selected_art23_2_tier(m100_tier_edition_snapshot, tier, expected)


def test_0150_unchecked_eligibility_does_not_require_or_apply_tier(
    m100_tier_edition_snapshot: RegistrySnapshot,
) -> None:
    scenarios.check_0150_unchecked_eligibility_does_not_require_or_apply_tier(m100_tier_edition_snapshot)


@pytest.mark.parametrize(
    "inputs",
    (
        {"0100": Decimal("1"), "0102": Decimal("100.00"), "0104": Decimal("100.00")},
        {"0100": Decimal("1"), "0102": Decimal("100.00"), "0104": Decimal("250.00")},
    ),
)
def test_0150_non_positive_0149_does_not_create_positive_reduction(
    m100_tier_edition_snapshot: RegistrySnapshot, inputs: dict[str, Decimal]
) -> None:
    scenarios.check_0150_non_positive_0149_does_not_create_positive_reduction(m100_tier_edition_snapshot, inputs)


def test_0150_positive_checked_rental_fails_closed_without_tier(m100_tier_edition_snapshot: RegistrySnapshot) -> None:
    scenarios.check_0150_positive_checked_rental_fails_closed_without_tier(m100_tier_edition_snapshot)


def test_0150_rejects_unknown_tier_key(m100_tier_edition_snapshot: RegistrySnapshot) -> None:
    scenarios.check_0150_rejects_unknown_tier_key(m100_tier_edition_snapshot)
