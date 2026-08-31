"""Malformed-value parity between modelo aux transport rows and their canonical models.

The audit, work-history, and Modelo 190 breakdown transport rows redeclared
their fields as free strings and unconstrained integers while the canonical
models they project close the same axes to enums, hex-64 identities, bounded
identifiers, aware timestamps, and non-negative magnitudes. A value the
canonical model refuses could therefore still cross the CLI envelope.

Each test here asserts the transport row now refuses what its canonical
counterpart refuses, and — the control that makes the refusals meaningful —
that a well-formed row still validates and still renders the same JSON wire
shape (enum values as their strings, timestamps as ISO text).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from ....application.evidence import BundleVerificationState
from ....core.aggregation import RetencionClave
from ....domain.buckets import BucketEventObjectType, BucketEventType
from .._modelo_aux_payloads import (
    EvidenceRecordRefPayload,
    ModeloAuditViewResult,
    WithholdingClaveBreakdownPayload,
    WorkUnitHistoryEventPayload,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_HEX64 = "a" * 64
_DIGEST = "b" * 64
_WHEN = datetime(2026, 4, 1, 10, 30, tzinfo=UTC)


def _event(**overrides: Any) -> WorkUnitHistoryEventPayload:
    fields: dict[str, Any] = {
        "event_id": _HEX64,
        "occurred_at": _WHEN,
        "event_type": BucketEventType.MODELO_WORK_UNIT_CREATED,
        "object_type": BucketEventObjectType.WORK_UNIT,
        "object_id": "wu-1",
        "actor": "cadrumo.app.modelo.calculate",
        "payload": {},
    }
    fields.update(overrides)
    return WorkUnitHistoryEventPayload(**fields)  # type: ignore[arg-type]


def _record(**overrides: Any) -> EvidenceRecordRefPayload:
    fields: dict[str, Any] = {
        "object_type": BucketEventObjectType.WORK_UNIT,
        "object_id": "wu-1",
        "content_sha256": _DIGEST,
        "payload_size_bytes": 3,
    }
    fields.update(overrides)
    return EvidenceRecordRefPayload(**fields)  # type: ignore[arg-type]


class TestWithholdingClaveBreakdown:
    """Modelo 190 per-clave counts and monetary totals."""

    def test_well_formed_row_validates(self) -> None:
        row = WithholdingClaveBreakdownPayload(
            clave=RetencionClave.A,
            percepcion_count=2,
            percibido_total="1200.00",
            retencion_total="180.00",
        )
        assert row.model_dump(mode="json")["clave"] == RetencionClave.A.value

    def test_negative_perception_count_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            WithholdingClaveBreakdownPayload(
                clave=RetencionClave.A,
                percepcion_count=-1,
                percibido_total="1200.00",
                retencion_total="180.00",
            )

    @pytest.mark.parametrize("total", ["not-decimal", "NaN", "Infinity", "-1.00", "1.234,56", "1e3"])
    def test_non_decimal_or_negative_total_is_refused(self, total: str) -> None:
        with pytest.raises(ValidationError):
            WithholdingClaveBreakdownPayload(
                clave=RetencionClave.A,
                percepcion_count=1,
                percibido_total=total,
                retencion_total="180.00",
            )


class TestEvidenceRecordRef:
    """Evidence bundle record references."""

    def test_well_formed_record_validates(self) -> None:
        assert _record().model_dump(mode="json")["object_type"] == BucketEventObjectType.WORK_UNIT.value

    def test_bogus_object_type_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            _record(object_type="bogus")

    def test_negative_payload_size_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            _record(payload_size_bytes=-1)

    def test_empty_object_id_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            _record(object_id="")


class TestModeloAuditViewResult:
    """Evidence bundle manifest envelope."""

    def _bundle(self, **overrides: Any) -> ModeloAuditViewResult:
        fields: dict[str, Any] = {
            "bundle_id": _HEX64,
            "manifest_version": 1,
            "bucket_id": "bucket-one",
            "work_unit_id": _HEX64,
            "verification_state": BundleVerificationState.PENDING,
            "completeness_ratio": 1.0,
            "records": [_record()],
            "created_at": _WHEN,
        }
        fields.update(overrides)
        return ModeloAuditViewResult.model_validate(fields)

    def test_well_formed_bundle_renders_wire_shape(self) -> None:
        wire = self._bundle().model_dump(mode="json")
        assert wire["verification_state"] == BundleVerificationState.PENDING.value
        assert wire["created_at"].startswith("2026-04-01T10:30")

    def test_bogus_bundle_id_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            self._bundle(bundle_id="bad")

    def test_zero_manifest_version_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            self._bundle(manifest_version=0)

    def test_empty_bucket_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            self._bundle(bucket_id="")

    def test_bogus_verification_state_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            self._bundle(verification_state="bogus")

    @pytest.mark.parametrize("ratio", [2.0, -0.5])
    def test_out_of_range_completeness_is_refused(self, ratio: float) -> None:
        with pytest.raises(ValidationError):
            self._bundle(completeness_ratio=ratio)

    def test_non_date_created_at_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            self._bundle(created_at="not-date")


class TestWorkUnitHistoryEvent:
    """Work-unit history rows projected from canonical bucket events."""

    def test_well_formed_event_renders_wire_shape(self) -> None:
        wire = _event().model_dump(mode="json")
        assert wire["event_type"] == BucketEventType.MODELO_WORK_UNIT_CREATED.value
        assert wire["occurred_at"].startswith("2026-04-01T10:30")

    def test_bogus_event_id_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            _event(event_id="bad")

    def test_non_date_occurred_at_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            _event(occurred_at="not-date")

    def test_bogus_event_type_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            _event(event_type="bogus")

    def test_bogus_object_type_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            _event(object_type="bogus")

    def test_empty_object_id_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            _event(object_id="")

    @pytest.mark.parametrize("actor", ["", "x" * 65])
    def test_out_of_bounds_actor_is_refused(self, actor: str) -> None:
        with pytest.raises(ValidationError):
            _event(actor=actor)
