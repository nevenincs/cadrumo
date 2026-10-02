"""Period-scope requirements for the canonical application-owned Modelo reader."""

from __future__ import annotations

from uuid import uuid4

import pytest

from ....core.period import Period
from ...operations.public_period import PublicPeriod
from ..query_read_operation import (
    ModeloBindingsListRequest,
    ModeloReadinessOperationRequest,
    _requested_scope,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_scope_requires_all_periods_when_a_read_is_not_exact() -> None:
    """A missing-binding or periodless readiness query cannot borrow one period."""
    profile_id = uuid4()
    annual = Period.from_year_and_code(2026, "0A")
    assert _requested_scope(ModeloBindingsListRequest(profile_id=profile_id)) == (frozenset(), True, False)
    assert _requested_scope(ModeloBindingsListRequest(profile_id=profile_id, missing=True)) == (
        frozenset(),
        True,
        True,
    )
    assert _requested_scope(
        ModeloBindingsListRequest(profile_id=profile_id, year=2026, period_code="0A", missing=True)
    ) == (
        frozenset({annual}),
        False,
        False,
    )
    assert _requested_scope(ModeloReadinessOperationRequest(profile_id=profile_id, modelo="303", filing_year=2026)) == (
        frozenset(),
        True,
        True,
    )
    assert _requested_scope(
        ModeloReadinessOperationRequest(
            profile_id=profile_id,
            modelo="303",
            filing_year=2026,
            period=PublicPeriod.from_period(annual),
        )
    ) == (frozenset({annual}), False, False)
