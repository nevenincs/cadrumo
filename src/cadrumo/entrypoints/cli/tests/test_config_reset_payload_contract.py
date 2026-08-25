"""Contract parity between the durable reset journal and its CLI projection.

``ConfigResetOperationPayload`` and its nested target/summary payloads must
refuse the malformed operation-id, status, phase, pause-reason, timestamp,
and completion-count shapes the canonical ``ConfigResetOperation`` journal
already refuses, and must accept the same journal a real reset run produces.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ....application._config_reset_models import (
    ConfigResetOperation,
    ConfigResetOperationStatus,
    ConfigResetPointerSnapshot,
    ConfigResetSummary,
    ConfigResetTarget,
    ConfigResetTargetPhase,
)
from ....core import STR_KEYED_MAPPING_ADAPTER, BucketPointer
from .._config_payloads import ConfigResetOperationPayload

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_OPERATION_ID = "a" * 64
_STARTED_AT = datetime(2026, 6, 1, 8, 0, tzinfo=UTC)
_COMPLETED_AT = datetime(2026, 6, 1, 8, 5, tzinfo=UTC)


def _completed_operation() -> ConfigResetOperation:
    target = ConfigResetTarget(
        bucket_id="alpha",
        exists_at_snapshot=False,
        phase=ConfigResetTargetPhase.DELETED,
        completed_at=_COMPLETED_AT,
    )
    return ConfigResetOperation(
        operation_id=_OPERATION_ID,
        status=ConfigResetOperationStatus.COMPLETE,
        started_at=_STARTED_AT,
        updated_at=_COMPLETED_AT,
        pointer_snapshot=ConfigResetPointerSnapshot(record=BucketPointer.absent(transition_revision=0)),
        targets=(target,),
        summary=ConfigResetSummary(
            target_count=1,
            deleted_count=0,
            already_absent_count=1,
            retention_override_count=0,
            completed_at=_COMPLETED_AT,
        ),
    )


def test_projection_round_trips_a_real_completed_journal() -> None:
    """A genuine journal the reset service produces projects and validates cleanly."""
    operation = _completed_operation()

    payload = ConfigResetOperationPayload.from_operation(operation)

    assert payload.operation_id == operation.operation_id
    assert payload.status is ConfigResetOperationStatus.COMPLETE
    assert payload.summary is not None
    assert payload.summary.target_count == 1


def _payload_kwargs(**overrides: object) -> dict[str, object]:
    payload = ConfigResetOperationPayload.from_operation(_completed_operation())
    base = STR_KEYED_MAPPING_ADAPTER.validate_python(payload.model_dump(mode="json"))
    base.update(overrides)
    return base


def _mutable_payload_mapping(value: object) -> dict[str, object]:
    """Narrow a JSON object before a malformed-input test mutates it."""
    assert isinstance(value, dict)
    return STR_KEYED_MAPPING_ADAPTER.validate_python(value)


def test_malformed_operation_id_is_refused() -> None:
    """A non hex-64 operation id crosses the canonical journal's own identity shape."""
    with pytest.raises(ValidationError):
        ConfigResetOperationPayload.model_validate(_payload_kwargs(operation_id="bad"))


def test_unknown_status_is_refused() -> None:
    """The canonical journal's closed status vocabulary must reject a free string."""
    with pytest.raises(ValidationError):
        ConfigResetOperationPayload.model_validate(_payload_kwargs(status="bogus"))


def test_malformed_started_at_is_refused() -> None:
    """A non-ISO timestamp fails the same UTC-aware parity the journal enforces."""
    with pytest.raises(ValidationError):
        ConfigResetOperationPayload.model_validate(_payload_kwargs(started_at="not-a-time"))


def test_updated_at_before_started_at_is_refused() -> None:
    """Journal ordering (updated_at may never precede started_at) survives projection."""
    with pytest.raises(ValidationError):
        ConfigResetOperationPayload.model_validate(
            _payload_kwargs(updated_at=_STARTED_AT.isoformat(), started_at=_COMPLETED_AT.isoformat()),
        )


def test_unsorted_paused_target_ids_are_refused() -> None:
    """Paused target ids must stay unique and sorted, matching the journal invariant."""
    payload = _payload_kwargs(
        status=ConfigResetOperationStatus.PAUSED.value,
        pause_reason="retention_unresolved",
        paused_target_ids=["beta", "alpha"],
        summary=None,
    )
    with pytest.raises(ValidationError):
        ConfigResetOperationPayload.model_validate(payload)


def test_malformed_target_lifecycle_stage_is_refused() -> None:
    """A target row's lifecycle stage must stay within the canonical closed vocabulary."""
    payload = _payload_kwargs()
    targets = payload["targets"]
    assert isinstance(targets, list)
    _mutable_payload_mapping(targets[0])["phase"] = "bogus"
    with pytest.raises(ValidationError):
        ConfigResetOperationPayload.model_validate(payload)


def test_blank_target_bucket_id_is_refused() -> None:
    """A target row's bucket id must stay non-blank, matching the journal invariant."""
    payload = _payload_kwargs()
    targets = payload["targets"]
    assert isinstance(targets, list)
    _mutable_payload_mapping(targets[0])["bucket_id"] = ""
    with pytest.raises(ValidationError):
        ConfigResetOperationPayload.model_validate(payload)


def test_mismatched_completion_counts_are_refused() -> None:
    """A self-reconciling summary whose counts diverge from the actual targets is refused.

    ``deleted_count=1, already_absent_count=0`` sums to the summary's own
    ``target_count=1``, so the flat summary invariant alone would pass; the
    single target is snapshotted absent (``exists_at_snapshot=False``), so
    the operation-level reconciliation against the real targets must catch
    the mismatch.
    """
    payload = _payload_kwargs()
    summary = _mutable_payload_mapping(payload["summary"])
    summary["deleted_count"] = 1
    summary["already_absent_count"] = 0
    with pytest.raises(ValidationError):
        ConfigResetOperationPayload.model_validate(payload)
