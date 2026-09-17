"""Scope and temporal-admission contracts for the M130 prior-payment advisory."""

from __future__ import annotations

import pytest

from ....core.authority_grade import RegistryAuthorityGrade
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ..prior_payment_advisory import _PriorPaymentDeclaration, _selected_registry_declaration

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ANNUAL_PERIOD = "0A"
_FIRST_QUARTER = "1T"


def test_non_m130_work_does_not_apply_the_m130_declaration(operation: PinnedAuthorityOperation) -> None:
    revision = published_snapshot(
        "200",
        filing_year=2024,
        period=_ANNUAL_PERIOD,
        grade=RegistryAuthorityGrade.CALCULATION,
    ).revision

    assert (
        _selected_registry_declaration(
            revision,
            modelo="200",
            filing_year=2024,
            period_token=_ANNUAL_PERIOD,
            operation=operation,
        )
        is None
    )


def test_m130_work_uses_its_filing_year_scoped_period_query(operation: PinnedAuthorityOperation) -> None:
    revision = published_snapshot(
        "130",
        filing_year=2024,
        period=_FIRST_QUARTER,
    ).revision

    resolved = _selected_registry_declaration(
        revision,
        modelo="130",
        filing_year=2024,
        period_token=_FIRST_QUARTER,
        operation=operation,
    )

    assert isinstance(resolved, _PriorPaymentDeclaration)
    assert resolved.modelo == "130"
    assert (
        len(
            {
                resolved.prior_payment,
                resolved.cumulative_income,
                resolved.prior_positive_part,
                resolved.prior_minoracion,
            }
        )
        == 4
    )
