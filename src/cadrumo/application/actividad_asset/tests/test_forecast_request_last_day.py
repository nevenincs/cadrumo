"""A forecast request ends its interval at the exclusive boundary or at the last day covered."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from cadrumo.application.actividad_asset.activity_asset_contracts import ActivityAssetForecastRequest
from cadrumo.application.actividad_asset.operations import ActivityAssetOperations
from cadrumo.core.hashing import content_hash_hex
from cadrumo.domain.renta.actividad_asset.election import DirectEstimationRegime
from cadrumo.domain.renta.actividad_asset.register_records import ActivityAssetDescriptorFacts
from cadrumo.domain.renta.actividad_asset.schedule import covered_until_after, last_day_covered

from .ledger_support import MemoryLedger, acquisition_transaction
from .operations_support import build_forecast, build_revision
from .register_support import MemoryRepository, memory_register_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = uuid4()
ACQUISITION = acquisition_transaction()


def _decode(**interval: str | None) -> ActivityAssetForecastRequest:
    document = {"profile_id": str(_PROFILE), "asset_id": "laptop-1", "covered_from": "2025-01-01", **interval}
    return ActivityAssetForecastRequest.model_validate_json(json.dumps(document))


def test_the_boundary_inverts_the_last_day() -> None:
    for boundary in (date(2025, 7, 1), date(2026, 1, 1), date(2024, 3, 1)):
        assert covered_until_after(last_day_covered(boundary)) == boundary


def test_a_last_day_decodes_to_the_boundary_the_operations_compute_with() -> None:
    from_boundary = _decode(covered_until="2025-07-01")
    from_last_day = _decode(covered_through="2025-06-30")
    from_both = _decode(covered_until="2025-07-01", covered_through="2025-06-30")

    assert from_last_day.exclusive_end() == date(2025, 7, 1)
    assert from_boundary.covered_through == date(2025, 6, 30)
    assert from_last_day == from_boundary
    assert from_both == from_boundary
    assert from_both.model_dump_json() == from_boundary.model_dump_json() == from_last_day.model_dump_json()
    assert content_hash_hex(from_last_day.model_dump(mode="json")) == content_hash_hex(
        from_boundary.model_dump(mode="json")
    )


def test_a_year_end_last_day_reaches_the_next_new_year() -> None:
    assert _decode(covered_through="2025-12-31").exclusive_end() == date(2026, 1, 1)


@pytest.mark.parametrize(
    "interval",
    [
        {"covered_until": "2025-07-01", "covered_through": "2025-07-01"},
        {"covered_until": "2025-07-01", "covered_through": "2025-06-29"},
        {},
        {"covered_through": "not a date"},
        {"covered_through": "9999-12-31"},
        {"covered_until": None, "covered_through": None},
    ],
)
def test_a_disagreeing_or_missing_end_is_refused(interval: dict[str, str | None]) -> None:
    with pytest.raises(ValidationError):
        _decode(**interval)


def test_the_stated_form_does_not_change_the_forecast_or_its_fingerprint() -> None:
    operations = ActivityAssetOperations(
        repository=MemoryRepository(),
        ledger=MemoryLedger(ACQUISITION),
        forecast_operation=build_forecast,
        taxpayer_modality=lambda: DirectEstimationRegime.SIMPLIFIED,
        register_authority=memory_register_authority(),
    )
    operations.create(build_revision(), ActivityAssetDescriptorFacts(name="Office laptop"))

    def forecast(request: ActivityAssetForecastRequest) -> object:
        return operations.forecast(
            asset_id=request.asset_id,
            covered_from=request.covered_from,
            covered_until=request.exclusive_end(),
        )

    exclusive = forecast(_decode(covered_until="2025-07-01"))
    inclusive = forecast(_decode(covered_through="2025-06-30"))

    assert inclusive == exclusive
    assert operations.forecast(
        asset_id="laptop-1", covered_from=date(2025, 1, 1), covered_until=date(2025, 7, 1)
    ).amount == Decimal("257.86")


def test_the_schema_offers_both_ends_as_optional_fields() -> None:
    schema = ActivityAssetForecastRequest.model_json_schema()

    assert {"covered_until", "covered_through"} <= set(schema["properties"])
    assert not {"covered_until", "covered_through"} & set(schema["required"])
