"""A refusal for overlapping claims serves the claims it conflicts with, through the operation's own refusal."""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.application.actividad_asset.activity_asset_executors import activity_asset_executors_refusal
from cadrumo.domain.renta.actividad_asset.errors import ActividadAssetClaimConflictError

from .test_register import NAME, full_year, register_operations, register_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FIRST = register_revision().in_service_date.year

_ASSET = "laptop-1"


def _refused_overlap() -> tuple[str, ActividadAssetClaimConflictError]:
    operations, _ = register_operations()
    operations.create(register_revision(), NAME)
    recorded = operations.record_claim(full_year(operations, _FIRST), creating_operation="test.year").claim
    inside = operations.forecast(asset_id=_ASSET, covered_from=date(_FIRST, 3, 1), covered_until=date(_FIRST, 5, 1))
    with pytest.raises(ActividadAssetClaimConflictError) as refused:
        operations.record_claim(inside, creating_operation="test.inside")
    return recorded.claim_id, refused.value


def test_an_overlap_refusal_serves_the_id_of_the_claim_it_overlaps() -> None:
    claim_id, error = _refused_overlap()

    assert error.translated_message == "ledger.actividad_asset.errors.claims_overlap"
    refusal = activity_asset_executors_refusal(error)
    assert refusal is not None
    assert refusal.reason_facts == {"conflicting_claim_ids": claim_id}


def test_an_overlap_with_two_claims_serves_both_ids_in_history_order() -> None:
    operations, _ = register_operations()
    operations.create(register_revision(), NAME)
    ids = [
        operations.record_claim(
            operations.forecast(asset_id=_ASSET, covered_from=start, covered_until=end), creating_operation=origin
        ).claim.claim_id
        for origin, start, end in (
            ("test.first", date(_FIRST, 1, 1), date(_FIRST, 3, 1)),
            ("test.second", date(_FIRST, 3, 1), date(_FIRST, 5, 1)),
        )
    ]
    across = operations.forecast(asset_id=_ASSET, covered_from=date(_FIRST, 2, 1), covered_until=date(_FIRST, 4, 1))

    with pytest.raises(ActividadAssetClaimConflictError) as refused:
        operations.record_claim(across, creating_operation="test.across")

    refusal = activity_asset_executors_refusal(refused.value)
    assert refusal is not None
    assert refusal.reason_facts == {"conflicting_claim_ids": ",".join(ids)}
