"""Scope and temporal-admission contracts for the M130 prior-payment advisory."""

from __future__ import annotations

import pytest

from ....core.authority_grade import RegistryAuthorityGrade
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.facts.resolution import ResolvedMappingFact
from ..prior_payment_advisory import _selected_registry_declaration

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ANNUAL_PERIOD = "0A"
_FIRST_QUARTER = "1T"


def test_non_m130_work_does_not_apply_the_m130_declaration() -> None:
    revision = bundled_authority().snapshot(
        "200",
        filing_year=2024,
        period=_ANNUAL_PERIOD,
        grade=RegistryAuthorityGrade.CALCULATION,
    ).revision

    assert _selected_registry_declaration(
        revision,
        modelo="200",
        filing_year=2024,
        period_token=_ANNUAL_PERIOD,
    ) is None


def test_m130_work_uses_its_filing_year_scoped_period_query() -> None:
    revision = bundled_authority().snapshot(
        "130",
        filing_year=2024,
        period=_FIRST_QUARTER,
    ).revision

    resolved = _selected_registry_declaration(
        revision,
        modelo="130",
        filing_year=2024,
        period_token=_FIRST_QUARTER,
    )

    assert isinstance(resolved, ResolvedMappingFact)
    assert resolved.variant_id == "m130-prior-payment-verification-mapping:2019-y-siguientes"
