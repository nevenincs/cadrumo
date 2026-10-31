"""A refusal about the end of a period or a baja states its last day as well as the boundary it computes with."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.core.i18n.render import tr
from cadrumo.domain.renta.actividad_asset.claims import effective_claims
from cadrumo.domain.renta.actividad_asset.errors import (
    ActividadAssetClaimConflictError,
    ActividadAssetPeriodElapsedError,
)
from cadrumo.domain.renta.actividad_asset.schedule import covered_until_after, last_day_covered

from .test_baja_correction import _disposed
from .test_register import _NAME, _full_year, _operations, _revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_the_two_boundary_helpers_are_inverse() -> None:
    boundary = date(2027, 1, 1)

    assert last_day_covered(boundary) == date(2026, 12, 31)
    assert covered_until_after(last_day_covered(boundary)) == boundary


def test_an_elapsed_period_states_the_day_it_ended_and_the_boundary_after_it() -> None:
    operations, _ = _operations(today=date(2037, 12, 31))
    operations.create(_revision(), _NAME)

    with pytest.raises(ActividadAssetPeriodElapsedError) as refused:
        _full_year(operations, 2036)

    facts = {name: str(value) for name, value in (refused.value.context or {}).items()}
    assert facts == {"ended_on": "2034-12-31", "ended_before": "2035-01-01"}
    assert refused.value.translated_message is not None
    rendered = tr(refused.value.translated_message, **facts)
    assert "2034-12-31" in rendered
    assert "2035-01-01" not in rendered


def test_a_claim_past_the_baja_states_the_last_days_beside_the_boundaries() -> None:
    _, repository, _ = _disposed()
    shortened = next(claim for claim in effective_claims(repository.history.claims) if claim.tax_year == 2026)
    later = shortened.model_copy(
        update={
            "tax_year": 2028,
            "covered_from": date(2028, 1, 1),
            "covered_until": date(2029, 1, 1),
            "amount": Decimal("10.00"),
            "supersedes_claim_id": None,
            "disposal_revision_id": None,
        },
    )

    with pytest.raises(ActividadAssetClaimConflictError) as refused:
        repository.history.record_claim(later)

    facts = {name: str(value) for name, value in (refused.value.context or {}).items()}
    assert facts == {
        "covered_until": "2029-01-01",
        "covered_through": "2028-12-31",
        "boundary": "2026-07-01",
        "boundary_through": "2026-06-30",
    }
    assert refused.value.translated_message is not None
    rendered = tr(refused.value.translated_message, **facts)
    assert "2028-12-31" in rendered
    assert "2026-06-30" in rendered


def test_the_election_limits_state_the_last_day_of_the_period_beside_the_boundary() -> None:
    operations, _ = _operations()
    operations.create(_revision(), _NAME)

    limits = operations.plan_limits("laptop-1")

    assert limits.maximum_period_ends_on == date(2035, 1, 1)
    assert limits.maximum_period_last_day == date(2034, 12, 31)
