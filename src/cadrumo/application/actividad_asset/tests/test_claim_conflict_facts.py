"""A refusal for overlapping claims serves the claims it conflicts with, through the operation's own refusal."""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.application.actividad_asset.activity_asset_executors import _refusal
from cadrumo.domain.renta.actividad_asset.errors import ActividadAssetClaimConflictError

from .test_register import _NAME, _full_year, _operations, _revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ASSET = "laptop-1"


def _refused_overlap() -> tuple[str, ActividadAssetClaimConflictError]:
    operations, _ = _operations()
    operations.create(_revision(), _NAME)
    recorded = operations.record_claim(_full_year(operations, 2025), creating_operation="test.year").claim
    inside = operations.forecast(asset_id=_ASSET, covered_from=date(2025, 3, 1), covered_until=date(2025, 5, 1))
    with pytest.raises(ActividadAssetClaimConflictError) as refused:
        operations.record_claim(inside, creating_operation="test.inside")
    return recorded.claim_id, refused.value


def test_an_overlap_refusal_serves_the_id_of_the_claim_it_overlaps() -> None:
    claim_id, error = _refused_overlap()

    assert error.translated_message == "ledger.actividad_asset.errors.claims_overlap"
    refusal = _refusal(error)
    assert refusal is not None
    assert refusal.reason_facts == {"conflicting_claim_ids": claim_id}


def test_an_overlap_with_two_claims_serves_both_ids_in_history_order() -> None:
    operations, _ = _operations()
    operations.create(_revision(), _NAME)
    ids = [
        operations.record_claim(
            operations.forecast(asset_id=_ASSET, covered_from=start, covered_until=end), creating_operation=origin
        ).claim.claim_id
        for origin, start, end in (
            ("test.first", date(2025, 1, 1), date(2025, 3, 1)),
            ("test.second", date(2025, 3, 1), date(2025, 5, 1)),
        )
    ]
    across = operations.forecast(asset_id=_ASSET, covered_from=date(2025, 2, 1), covered_until=date(2025, 4, 1))

    with pytest.raises(ActividadAssetClaimConflictError) as refused:
        operations.record_claim(across, creating_operation="test.across")

    refusal = _refusal(refused.value)
    assert refusal is not None
    assert refusal.reason_facts == {"conflicting_claim_ids": ",".join(ids)}
