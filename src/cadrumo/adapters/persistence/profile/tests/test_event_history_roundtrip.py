"""Strict roundtrip across the encrypted bucket-event-history boundary.

:class:`BucketEventHistoryRepository` persists the append-only audit
log of bucket events through :class:`SecureObjectRepository`. This
test asserts the save / load cycle preserves every event, the
catalogue keying by content-addressed event_id, and the per-event
typed payload mapping.

Real active-profile runtime, real SQLite, no mocks.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from .....core.classification.policies import SensitivityClass
from .....domain.buckets.event import (
    BucketEvent,
    BucketEventHistoryCatalogue,
    BucketEventObjectType,
    BucketEventType,
    derive_bucket_event_id,
)
from .....domain.buckets.event_repository import BucketEventHistoryPersistenceError
from .....tests.secure_sql import isolated_runtime_profile, mutate_encrypted_secure_object_json
from ...storage.envelope.contract import Envelope
from ..buckets import (
    _CATALOGUE_VERSION,
    _NAMESPACE,
    _OBJECT_KEY,
    BucketEventHistoryRepository,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_OCCURRED_AT = datetime(2026, 5, 28, 9, 0, 0, tzinfo=UTC)


def _build_event(
    *,
    bucket_id: str,
    event_type: BucketEventType,
    occurred_at: datetime,
    actor: str,
    object_type: BucketEventObjectType,
    object_id: str,
    payload: dict[str, str],
) -> BucketEvent:
    return BucketEvent(
        event_id=derive_bucket_event_id(
            bucket_id=bucket_id,
            event_type=event_type,
            occurred_at=occurred_at,
            actor=actor,
            object_type=object_type,
            object_id=object_id,
            payload=payload,
        ),
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor,
        object_type=object_type,
        object_id=object_id,
        payload_version=1,
        payload=payload,
    )


def test_bucket_event_history_survives_encrypted_storage_roundtrip(
    tmp_path: Path,
) -> None:
    """The full event-history catalogue round-trips strictly under encryption."""

    with isolated_runtime_profile(tmp_path=tmp_path):
        bucket_id = "b" * 32
        event_a = _build_event(
            bucket_id=bucket_id,
            event_type=BucketEventType.MODELO_CALCULATION_CREATED,
            occurred_at=_OCCURRED_AT,
            actor="cli/aeat",
            object_type=BucketEventObjectType.CALCULATION_REVISION,
            object_id="r" * 64,
            payload={"modelo": "303", "filing_year": "2025", "period": "1T"},
        )
        event_b = _build_event(
            bucket_id=bucket_id,
            event_type=BucketEventType.PROFILE_SELECTED,
            occurred_at=_OCCURRED_AT,
            actor="cli/aeat",
            object_type=BucketEventObjectType.PROFILE,
            object_id="profile-active",
            payload={},
        )
        catalogue = BucketEventHistoryCatalogue(
            events={event_a.event_id: event_a, event_b.event_id: event_b},
        )

        repo = BucketEventHistoryRepository()
        repo.save(catalogue)
        loaded = repo.load()

        assert loaded == catalogue
        loaded_a = loaded.events[event_a.event_id]
        assert loaded_a.payload == {"modelo": "303", "filing_year": "2025", "period": "1T"}
        assert loaded_a.event_type is BucketEventType.MODELO_CALCULATION_CREATED
        assert loaded_a.object_type is BucketEventObjectType.CALCULATION_REVISION
        loaded_b = loaded.events[event_b.event_id]
        assert loaded_b.payload == {}
        assert loaded_b.event_type is BucketEventType.PROFILE_SELECTED


def test_bucket_event_payload_tampering_surfaces_at_load(tmp_path: Path) -> None:
    """Anti-tautology proof: mutating an event's payload must surface.

    Every :class:`BucketEvent` carries a content-addressed
    ``event_id`` derived from the full event shape including its
    payload. The model_validator re-derives the id on every
    construction. A persisted event whose payload is mutated post-
    save MUST fail the id check on load — that's the audit-trail
    integrity guarantee the catalogue relies on.

    Persists one event, reaches into ``SecureObjectRow`` via
    ``session_scope``, surgically rewrites a payload value (changing
    ``modelo`` from ``"303"`` to ``"100"`` without touching the
    event_id), and asserts the load path catches the drift via the
    model_validator's derived-id check.

    If this test passes silently with a tampered payload, the bucket-
    event-history boundary is tautological and the audit trail is
    not actually content-addressed.
    """

    from sqlalchemy import select

    from ...storage.sql import SecureObjectRow

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        bucket_id = "b" * 32
        event = _build_event(
            bucket_id=bucket_id,
            event_type=BucketEventType.MODELO_CALCULATION_CREATED,
            occurred_at=_OCCURRED_AT,
            actor="cli/aeat",
            object_type=BucketEventObjectType.CALCULATION_REVISION,
            object_id="r" * 64,
            payload={"modelo": "303", "filing_year": "2025", "period": "1T"},
        )
        catalogue = BucketEventHistoryCatalogue(events={event.event_id: event})
        repo = BucketEventHistoryRepository()
        repo.save(catalogue)

        stmt = select(SecureObjectRow).where(
            SecureObjectRow.namespace == _NAMESPACE,
        )

        def mutate(envelope):
            events = envelope["payload"]["events"]
            event_dict = events[event.event_id]
            assert event_dict["payload"]["modelo"] == "303", (
                "fixture must serialise the modelo payload key as '303' for this proof test to be meaningful"
            )
            event_dict["payload"]["modelo"] = "100"

        mutate_encrypted_secure_object_json(profile.repository._engine, row_statement=stmt, mutate=mutate)

        with pytest.raises(BucketEventHistoryPersistenceError) as exc_info:
            repo.load()

        assert exc_info.value.translated_message == "errors.storage.stored_data_validation_boundary"
        assert exc_info.value.context == {
            "namespace": _NAMESPACE,
            "object_key": _OBJECT_KEY,
        }


def test_bucket_event_inner_classification_drift_is_structured(tmp_path: Path) -> None:
    """Inner envelope classification drift is rejected after secure-object decrypts."""

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        catalogue = BucketEventHistoryCatalogue()
        repo = BucketEventHistoryRepository()
        repo.save(catalogue)
        record = profile.repository.load(
            _NAMESPACE,
            _OBJECT_KEY,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_CATALOGUE_VERSION,
        )
        assert record is not None
        envelope = Envelope[BucketEventHistoryCatalogue].model_validate_json(record.payload)
        profile.repository.save(
            namespace=record.namespace,
            object_key=_OBJECT_KEY,
            classification=record.classification,
            schema_version=record.schema_version,
            written_at=record.written_at,
            payload=envelope.model_copy(update={"classification": SensitivityClass.AUDIT})
            .model_dump_json()
            .encode("utf-8"),
        )

        with pytest.raises(BucketEventHistoryPersistenceError) as exc_info:
            repo.load()

        assert exc_info.value.translated_message == "errors.integrity.integrity_storage_classification"
        assert exc_info.value.context == {
            "namespace": _NAMESPACE,
            "object_key": _OBJECT_KEY,
            "classification": SensitivityClass.AUDIT.value,
            "expected": SensitivityClass.FINANCIAL.value,
        }


def test_bucket_event_inner_schema_version_drift_is_structured(tmp_path: Path) -> None:
    """Inner envelope schema-version drift is rejected after secure-object decrypts."""

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        catalogue = BucketEventHistoryCatalogue()
        repo = BucketEventHistoryRepository()
        repo.save(catalogue)
        record = profile.repository.load(
            _NAMESPACE,
            _OBJECT_KEY,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_CATALOGUE_VERSION,
        )
        assert record is not None
        envelope = Envelope[BucketEventHistoryCatalogue].model_validate_json(record.payload)
        profile.repository.save(
            namespace=record.namespace,
            object_key=_OBJECT_KEY,
            classification=record.classification,
            schema_version=record.schema_version,
            written_at=record.written_at,
            payload=envelope.model_copy(update={"schema_version": _CATALOGUE_VERSION + 1})
            .model_dump_json()
            .encode("utf-8"),
        )

        with pytest.raises(BucketEventHistoryPersistenceError) as exc_info:
            repo.load()

        assert exc_info.value.translated_message == "errors.integrity.integrity_storage_envelope_version"
        assert exc_info.value.context == {
            "namespace": _NAMESPACE,
            "object_key": _OBJECT_KEY,
            "schema_version": _CATALOGUE_VERSION + 1,
            "expected": _CATALOGUE_VERSION,
        }
