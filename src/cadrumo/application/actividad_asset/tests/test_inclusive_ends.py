"""A refusal about the end of a period or a baja states its last day as well as the boundary it computes with."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.core.config import override_settings
from cadrumo.core.i18n.render import tr
from cadrumo.domain.renta.actividad_asset.claims import effective_claims
from cadrumo.domain.renta.actividad_asset.errors import (
    ActividadAssetClaimConflictError,
    ActividadAssetPeriodElapsedError,
)
from cadrumo.domain.renta.actividad_asset.schedule import covered_until_after, last_day_covered

from .test_baja_correction import disposed
from .test_register import NAME, full_year, register_operations, register_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FIRST = register_revision().in_service_date.year


def test_the_two_boundary_helpers_are_inverse() -> None:
    boundary = date(_FIRST + 2, 1, 1)

    assert last_day_covered(boundary) == date(_FIRST + 1, 12, 31)
    assert covered_until_after(last_day_covered(boundary)) == boundary


def test_an_elapsed_period_states_the_day_it_ended_and_the_boundary_after_it() -> None:
    operations, _ = register_operations(today=date(_FIRST + 12, 12, 31))
    operations.create(register_revision(), NAME)

    with pytest.raises(ActividadAssetPeriodElapsedError) as refused:
        full_year(operations, _FIRST + 11)

    facts = {name: str(value) for name, value in (refused.value.context or {}).items()}
    assert facts == {
        "ended_on": date(_FIRST + 9, 12, 31).isoformat(),
        "ended_before": date(_FIRST + 10, 1, 1).isoformat(),
    }
    assert refused.value.translated_message is not None
    rendered = tr(refused.value.translated_message, **facts)
    assert date(_FIRST + 9, 12, 31).isoformat() in rendered
    assert date(_FIRST + 10, 1, 1).isoformat() not in rendered


def test_a_claim_past_the_baja_states_the_last_days_beside_the_boundaries() -> None:
    _, repository, _ = disposed()
    shortened = next(claim for claim in effective_claims(repository.history.claims) if claim.tax_year == _FIRST + 1)
    later = shortened.model_copy(
        update={
            "tax_year": _FIRST + 3,
            "covered_from": date(_FIRST + 3, 1, 1),
            "covered_until": date(_FIRST + 4, 1, 1),
            "amount": Decimal("10.00"),
            "supersedes_claim_id": None,
            "disposal_revision_id": None,
        },
    )

    with pytest.raises(ActividadAssetClaimConflictError) as refused:
        repository.history.record_claim(later)

    facts = {name: str(value) for name, value in (refused.value.context or {}).items()}
    assert facts == {
        "covered_until": date(_FIRST + 4, 1, 1).isoformat(),
        "covered_through": date(_FIRST + 3, 12, 31).isoformat(),
        "boundary": date(_FIRST + 1, 7, 1).isoformat(),
        "boundary_through": date(_FIRST + 1, 6, 30).isoformat(),
    }
    assert refused.value.translated_message is not None
    rendered = tr(refused.value.translated_message, **facts)
    assert date(_FIRST + 3, 12, 31).isoformat() in rendered
    assert date(_FIRST + 1, 6, 30).isoformat() in rendered


def test_the_election_limits_state_the_last_day_of_the_period_beside_the_boundary() -> None:
    operations, _ = register_operations()
    operations.create(register_revision(), NAME)

    limits = operations.plan_limits("laptop-1")

    assert limits.maximum_period_ends_on == date(_FIRST + 10, 1, 1)
    assert limits.maximum_period_last_day == date(_FIRST + 9, 12, 31)


@pytest.mark.parametrize("locale", ["en", "es", "ca", "hu"])
def test_the_baja_sentence_fills_in_every_placeholder_in_each_locale(locale: str) -> None:
    _, repository, _ = disposed()
    shortened = next(claim for claim in effective_claims(repository.history.claims) if claim.tax_year == _FIRST + 1)
    later = shortened.model_copy(
        update={
            "tax_year": _FIRST + 3,
            "covered_from": date(_FIRST + 3, 1, 1),
            "covered_until": date(_FIRST + 4, 1, 1),
            "amount": Decimal("10.00"),
            "supersedes_claim_id": None,
            "disposal_revision_id": None,
        },
    )
    with pytest.raises(ActividadAssetClaimConflictError) as refused:
        repository.history.record_claim(later)

    with override_settings(cadrumo_output_language=locale):
        assert refused.value.translated_message is not None
        rendered = tr(refused.value.translated_message, **dict(refused.value.context or {}))

    assert date(_FIRST + 3, 12, 31).isoformat() in rendered
    assert date(_FIRST + 1, 6, 30).isoformat() in rendered
    assert "%{" not in rendered
    assert "{" not in rendered
