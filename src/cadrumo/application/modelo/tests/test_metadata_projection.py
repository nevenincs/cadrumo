"""Canonical work metadata remains bound across public operation results."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ....core.period import Period
from ....domain.modelos.work_unit import WorkUnit, WorkUnitState, derive_work_unit_id
from ...operations.registry import OperationSchemaBindingV1
from ..metadata_projection import ModeloWorkMetadataSnapshot
from ..work_change_contracts import ModeloWorkDiscardPublicResultV2, ModeloWorkRenamePublicResultV2

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "5aa00000-0000-4000-8000-0000000000aa"
_CREATED = datetime(2026, 1, 10, 12, 0, tzinfo=UTC)
_UPDATED = datetime(2026, 2, 12, 12, 0, tzinfo=UTC)
_FILED_REVISION = "a" * 64
_FILING_RECORD = "b" * 64


def _unit(*, discarded: bool = False) -> WorkUnit:
    period = Period.from_year_and_code(2026, "1T")
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo="303",
            filing_year=2026,
            period=period,
            revision_id="test-revision",
        ),
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=2026,
        period=period,
        revision_id="test-revision",
        name="First-quarter return",
        created_at=_CREATED,
        updated_at=_UPDATED,
        state=WorkUnitState.DESCARTADO if discarded else WorkUnitState.BORRADOR,
        discarded_at=_UPDATED if discarded else None,
        discarded_by="Operator" if discarded else None,
        discard_reason="Duplicate work" if discarded else None,
        current_calculation_revision_id=_FILED_REVISION,
        filed_calculation_revision_id=_FILED_REVISION,
        current_filing_record_id=_FILING_RECORD,
    )


@pytest.mark.parametrize("discarded", [False, True])
def test_work_unit_metadata_survives_strict_json_roundtrip(discarded: bool) -> None:
    unit = _unit(discarded=discarded)
    snapshot = ModeloWorkMetadataSnapshot.from_work_unit(unit)

    restored = ModeloWorkMetadataSnapshot.model_validate_json(snapshot.model_dump_json())

    assert restored == snapshot
    assert restored.to_work_unit() == unit
    assert restored.period.filing_year == 2026
    assert restored.period.code == "1T"
    assert restored.filed_calculation_revision_id == _FILED_REVISION
    assert restored.current_filing_record_id == _FILING_RECORD
    assert restored.discarded_by == ("Operator" if discarded else None)
    assert restored.discard_reason == ("Duplicate work" if discarded else None)


@pytest.mark.parametrize(
    ("field", "altered"),
    [
        ("work_unit_id", "f" * 64),
        ("bucket_id", "6bb00000-0000-4000-8000-0000000000bb"),
        ("filing_year", 2025),
        ("period", {"filing_year": 2026, "code": "2T"}),
        ("state", "descartado"),
    ],
)
def test_snapshot_refuses_tampered_identity_period_profile_or_state(field: str, altered: object) -> None:
    payload = ModeloWorkMetadataSnapshot.from_work_unit(_unit()).model_dump(mode="json")
    payload[field] = altered

    with pytest.raises((ValidationError, ValueError)):
        ModeloWorkMetadataSnapshot.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize("result_type", [ModeloWorkRenamePublicResultV2, ModeloWorkDiscardPublicResultV2])
def test_v2_result_requires_exact_committed_unit_and_version(
    result_type: type[ModeloWorkRenamePublicResultV2] | type[ModeloWorkDiscardPublicResultV2],
) -> None:
    unit = _unit(discarded=result_type is ModeloWorkDiscardPublicResultV2)
    snapshot = ModeloWorkMetadataSnapshot.from_work_unit(unit)
    payload: dict[str, object] = {
        "result_version": 2,
        "work_unit_id": unit.work_unit_id,
        "bucket_id": unit.bucket_id,
        "unit": snapshot.model_dump(mode="json"),
    }
    if result_type is ModeloWorkRenamePublicResultV2:
        payload["name"] = unit.name
    else:
        payload["discarded"] = True
    schema = OperationSchemaBindingV1.bind(
        schema_id="modelo.work.rename.result"
        if result_type is ModeloWorkRenamePublicResultV2
        else "modelo.work.discard.result",
        schema_version=2,
        model_type=result_type,
    )
    assert schema.model_type is result_type
    assert result_type.model_validate_json(json.dumps(payload)).unit.to_work_unit() == unit

    for changed in (
        {**payload, "work_unit_id": "f" * 64},
        {**payload, "bucket_id": "6bb00000-0000-4000-8000-0000000000bb"},
        {**payload, "result_version": 1},
        {key: value for key, value in payload.items() if key != "unit"},
    ):
        with pytest.raises(ValidationError):
            result_type.model_validate_json(json.dumps(changed))

    if result_type is ModeloWorkRenamePublicResultV2:
        with pytest.raises(ValidationError):
            result_type.model_validate_json(json.dumps({**payload, "name": "A different name"}))
    else:
        for changed in (
            {**payload, "discarded": False},
            {**payload, "unit": ModeloWorkMetadataSnapshot.from_work_unit(_unit()).model_dump(mode="json")},
        ):
            with pytest.raises(ValidationError):
                result_type.model_validate_json(json.dumps(changed))
