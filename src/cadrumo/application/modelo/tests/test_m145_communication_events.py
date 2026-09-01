"""Bucket-event tests for Modelo 145 local communication records.

See Also:
    :mod:`~application.modelo._m145_communication_records`
        Backend service that emits communication-specific bucket events.
    :class:`~domain.buckets.BucketEvent`
        Bucket-local audit record asserted by this module.
    :class:`~domain.buckets.BucketEventType`
        Event-type vocabulary for create, export, delivery, and completion.
    :class:`~domain.buckets.BucketEventObjectType`
        Object-type vocabulary proving events name communication records.
    :func:`~application.modelo.export_m145_communication_record`
        Export operation whose event payload is checked here.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pytest

from ....adapters.outbound.aeat.export.registry_record_renderer import RegistryFixedWidthRecordRenderer
from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....domain.buckets.event import BucketEvent, BucketEventObjectType, BucketEventType
from ....tests.secure_sql import isolated_runtime_profile
from ..m145_communication_records import (
    M145CommunicationCreateCommand,
    create_m145_communication_record,
    export_m145_communication_record,
    mark_m145_communication_record_delivered_to_payer,
    mark_m145_communication_record_locally_completed,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ACTOR = "m145-event-test"
_FORBIDDEN_TERMS = (
    "filing",
    "filed",
    "deadline",
    "live_read",
    "portal",
    "submit",
    "receipt",
    "tramite",
    "tr\u00e1mite",
)


def _field_values(**overrides: str) -> dict[str, str]:
    values = {
        "perceptor.nif": "12345678Z",
        "perceptor.primer-apellido": "Garcia",
        "perceptor.segundo-apellido": "Lopez",
        "perceptor.nombre": "Ana",
        "perceptor.anio-nacimiento": "1981",
    }
    values.update(overrides)
    return values


def _command(*, field_values: dict[str, str] | None = None) -> M145CommunicationCreateCommand:
    return M145CommunicationCreateCommand(
        communication_year=2026,
        field_values=field_values if field_values is not None else _field_values(),
    )


def _events_for_record(
    repository: BucketEventHistoryRepository,
    communication_record_id: str,
) -> tuple[BucketEvent, ...]:
    return repository.load().for_object(
        object_type=BucketEventObjectType.COMMUNICATION_RECORD,
        object_id=communication_record_id,
    )


def _event_text(event: BucketEvent) -> str:
    payload_text = " ".join(f"{key}={value}" for key, value in sorted(event.payload.items()))
    return f"{event.event_type.value} {event.object_type.value} {event.actor} {payload_text}".lower()


def _assert_no_forbidden_terms(events: Iterable[BucketEvent]) -> None:
    for event in events:
        event_text = _event_text(event)
        for term in _FORBIDDEN_TERMS:
            assert term not in event_text


def test_m145_communication_lifecycle_emits_communication_specific_events(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        event_repository = BucketEventHistoryRepository(objects=runtime.repository)
        created = create_m145_communication_record(
            _command(),
            bucket_id=runtime.bucket_id,
            actor=_ACTOR,
            bucket_event_repository=event_repository,
        )
        exported = export_m145_communication_record(
            created.communication_record_id,
            bucket_id=runtime.bucket_id,
            renderer=RegistryFixedWidthRecordRenderer(),
            actor=_ACTOR,
            bucket_event_repository=event_repository,
        )
        mark_m145_communication_record_delivered_to_payer(
            created.communication_record_id,
            bucket_id=runtime.bucket_id,
            actor=_ACTOR,
            bucket_event_repository=event_repository,
        )
        mark_m145_communication_record_locally_completed(
            created.communication_record_id,
            bucket_id=runtime.bucket_id,
            actor=_ACTOR,
            bucket_event_repository=event_repository,
        )
        events = _events_for_record(event_repository, created.communication_record_id)

    events_by_type = {event.event_type: event for event in events}
    assert set(events_by_type) == {
        BucketEventType.MODELO_145_COMMUNICATION_CREATED,
        BucketEventType.MODELO_145_COMMUNICATION_EXPORTED,
        BucketEventType.MODELO_145_COMMUNICATION_DELIVERED_TO_PAYER,
        BucketEventType.MODELO_145_COMMUNICATION_LOCALLY_COMPLETED,
    }
    assert {event.object_type for event in events} == {BucketEventObjectType.COMMUNICATION_RECORD}
    assert {event.object_id for event in events} == {created.communication_record_id}
    assert {event.actor for event in events} == {_ACTOR}
    for event in events:
        assert event.bucket_id == runtime.bucket_id
        assert event.payload["communication_record_id"] == created.communication_record_id
        assert event.payload["modelo"] == "145"
        assert event.payload["communication_year"] == "2026"
        assert event.payload["period"] == "comunicacion"
        assert event.payload["revision_id"] == created.revision_id
        assert event.payload["state"] in {"created", "delivered_to_payer", "locally_completed"}

    export_event = events_by_type[BucketEventType.MODELO_145_COMMUNICATION_EXPORTED]
    assert export_event.payload["export_layout_id"] == exported.export_layout_id
    assert export_event.payload["payload_sha256"] == exported.payload_sha256
    assert export_event.payload["byte_length"] == str(exported.byte_length)
    assert export_event.payload["record_count"] == str(exported.record_count)
    _assert_no_forbidden_terms(events)


def test_m145_communication_idempotent_retries_do_not_duplicate_mutation_events(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        event_repository = BucketEventHistoryRepository(objects=runtime.repository)
        created = create_m145_communication_record(
            _command(),
            bucket_id=runtime.bucket_id,
            actor=_ACTOR,
            bucket_event_repository=event_repository,
        )
        create_m145_communication_record(
            _command(),
            bucket_id=runtime.bucket_id,
            actor=_ACTOR,
            bucket_event_repository=event_repository,
        )
        mark_m145_communication_record_delivered_to_payer(
            created.communication_record_id,
            bucket_id=runtime.bucket_id,
            actor=_ACTOR,
            bucket_event_repository=event_repository,
        )
        mark_m145_communication_record_delivered_to_payer(
            created.communication_record_id,
            bucket_id=runtime.bucket_id,
            actor=_ACTOR,
            bucket_event_repository=event_repository,
        )
        mark_m145_communication_record_locally_completed(
            created.communication_record_id,
            bucket_id=runtime.bucket_id,
            actor=_ACTOR,
            bucket_event_repository=event_repository,
        )
        mark_m145_communication_record_locally_completed(
            created.communication_record_id,
            bucket_id=runtime.bucket_id,
            actor=_ACTOR,
            bucket_event_repository=event_repository,
        )
        events = _events_for_record(event_repository, created.communication_record_id)

    event_types = [event.event_type for event in events]
    assert event_types.count(BucketEventType.MODELO_145_COMMUNICATION_CREATED) == 1
    assert event_types.count(BucketEventType.MODELO_145_COMMUNICATION_DELIVERED_TO_PAYER) == 1
    assert event_types.count(BucketEventType.MODELO_145_COMMUNICATION_LOCALLY_COMPLETED) == 1
    assert BucketEventType.MODELO_145_COMMUNICATION_EXPORTED not in event_types


def test_m145_communication_invalid_delivery_does_not_emit_delivery_event(tmp_path: Path) -> None:
    field_values = _field_values()
    field_values.pop("perceptor.nif")

    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        event_repository = BucketEventHistoryRepository(objects=runtime.repository)
        created = create_m145_communication_record(
            _command(field_values=field_values),
            bucket_id=runtime.bucket_id,
            actor=_ACTOR,
            bucket_event_repository=event_repository,
        )
        with pytest.raises(ValueError, match="validation passes"):
            mark_m145_communication_record_delivered_to_payer(
                created.communication_record_id,
                bucket_id=runtime.bucket_id,
                actor=_ACTOR,
                bucket_event_repository=event_repository,
            )
        events = _events_for_record(event_repository, created.communication_record_id)

    assert [event.event_type for event in events] == [BucketEventType.MODELO_145_COMMUNICATION_CREATED]
