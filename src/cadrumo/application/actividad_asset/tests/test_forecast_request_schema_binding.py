"""The forecast request remains canonical through public operation admission."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from cadrumo.application.actividad_asset.activity_asset_contracts import ActivityAssetForecastRequest
from cadrumo.application.operations.registry import OperationSchemaBindingV1
from cadrumo.application.operations.registry_schema_validation import strict_model_json_schema
from cadrumo.core.hashing import content_hash_hex
from cadrumo.domain.renta.actividad_asset.errors import ActividadAssetValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_direct_construction_normalizes_both_interval_forms() -> None:
    profile_id = uuid4()
    inclusive = ActivityAssetForecastRequest(
        profile_id=profile_id, asset_id="laptop-1", covered_from=date(2025, 1, 1), covered_through=date(2025, 6, 30)
    )
    exclusive = ActivityAssetForecastRequest(
        profile_id=profile_id, asset_id="laptop-1", covered_from=date(2025, 1, 1), covered_until=date(2025, 7, 1)
    )
    validated = ActivityAssetForecastRequest.model_validate(
        {
            "profile_id": profile_id,
            "asset_id": "laptop-1",
            "covered_from": date(2025, 1, 1),
            "covered_through": date(2025, 6, 30),
        }
    )

    assert inclusive.exclusive_end() == date(2025, 7, 1)
    assert inclusive.model_dump() == exclusive.model_dump() == validated.model_dump()
    assert inclusive.model_dump_json() == exclusive.model_dump_json() == validated.model_dump_json()


def test_minimum_boundary_decodes_and_is_refused_with_its_reason() -> None:
    request = ActivityAssetForecastRequest(
        profile_id=uuid4(), asset_id="laptop-1", covered_from=date.min, covered_until=date.min
    )

    with pytest.raises(ActividadAssetValidationError, match="covered_until_has_no_day_before"):
        request.exclusive_end()


def test_request_binds_to_its_closed_public_schema() -> None:
    schema = strict_model_json_schema(ActivityAssetForecastRequest)
    binding = OperationSchemaBindingV1.bind(
        schema_id="ledger.actividad-asset.forecast.request",
        schema_version=1,
        model_type=ActivityAssetForecastRequest,
    )

    properties = schema["properties"]
    required = schema["required"]
    assert isinstance(properties, dict)
    assert isinstance(required, list)
    assert {"covered_until", "covered_through"} <= set(properties)
    assert not {"covered_until", "covered_through"} & set(required)
    assert binding.identity.schema_fingerprint == content_hash_hex(schema)
