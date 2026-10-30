"""Forecast and claim snapshots state the last day they cover and take it back as input.

The stated day is display only: it joins neither the claim's identity nor any fingerprint,
so a claim recorded before the field existed keeps its id.
"""

from __future__ import annotations

import json
from datetime import date
from uuid import uuid4

import pytest
from pydantic import ValidationError

from cadrumo.application.actividad_asset.activity_asset_contracts import ActivityAssetClaimRequest
from cadrumo.application.actividad_asset.operation_dtos import (
    AmortizationClaimSnapshot,
    ScheduledAmortizationChargeSnapshot,
)
from cadrumo.domain.renta.actividad_asset.claims import AmortizationClaim
from cadrumo.domain.renta.actividad_asset.lifecycle import AssetKind

from .test_baja_correction import _ASSET, _disposed

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _forecast_json() -> str:
    operations, _, _ = _disposed()
    forecast = operations.forecast(asset_id=_ASSET, covered_from=date(2025, 1, 1), covered_until=date(2026, 1, 1))
    return ScheduledAmortizationChargeSnapshot.from_domain(forecast).model_dump_json()


def test_a_forecast_states_its_last_day_and_decodes_back_through_the_claim_request() -> None:
    snapshot = ScheduledAmortizationChargeSnapshot.model_validate_json(_forecast_json())

    assert snapshot.covered_through == date(2025, 12, 31)
    request = ActivityAssetClaimRequest(profile_id=uuid4(), forecast=snapshot)
    decoded = ActivityAssetClaimRequest.model_validate_json(request.model_dump_json())
    assert decoded.forecast.covered_through == date(2025, 12, 31)
    assert decoded.forecast.to_domain() == snapshot.to_domain()


def test_a_forecast_without_the_field_still_decodes() -> None:
    data = json.loads(_forecast_json())
    del data["covered_through"]

    snapshot = ScheduledAmortizationChargeSnapshot.model_validate_json(json.dumps(data))

    assert snapshot.covered_through is None
    assert snapshot.to_domain().covered_until == date(2026, 1, 1)


def test_a_forecast_with_a_wrong_last_day_is_refused_through_the_claim_request() -> None:
    data = json.loads(_forecast_json())
    data["covered_through"] = "2026-01-01"
    body = json.dumps({"profile_id": str(uuid4()), "forecast": data})

    with pytest.raises(ValidationError, match="covered_through"):
        ActivityAssetClaimRequest.model_validate_json(body)


def test_a_claim_snapshot_states_its_last_day_and_keeps_its_identity() -> None:
    operations, repository, _ = _disposed()
    claim: AmortizationClaim = next(item for item in repository.history.claims if item.tax_year == 2025)

    snapshot = AmortizationClaimSnapshot.from_domain(claim)
    decoded = AmortizationClaimSnapshot.model_validate_json(snapshot.model_dump_json())

    assert decoded.covered_through == date(2025, 12, 31)
    assert decoded.to_domain().claim_id == claim.claim_id
    assert claim.asset_kind is AssetKind.MATERIAL
    with pytest.raises(ValidationError, match="covered_through"):
        AmortizationClaimSnapshot.model_validate_json(
            json.dumps({**json.loads(snapshot.model_dump_json()), "covered_through": "2025-12-30"})
        )
    assert operations.list_elements()
