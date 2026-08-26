"""Real-runtime state transition tests for Modelo 145 local communication records.

See Also:
    :mod:`~application.modelo._m145_communication_records`
        Backend service implementing delivery and completion transitions.
    :class:`~application.modelo.M145CommunicationRecordState`
        State enum for created, delivered-to-payer, and locally-completed rows.
    :func:`~application.modelo.mark_m145_communication_record_delivered_to_payer`
        Public facade transition to payer-delivered state.
    :func:`~application.modelo.mark_m145_communication_record_locally_completed`
        Public facade transition to local-completion state.
    :func:`~application.modelo.read_m145_communication_record`
        Read-back path proving transitions persist in the encrypted store.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....domain.buckets import BucketEventType
from ....tests.secure_sql import isolated_runtime_profile
from ....tests.write_unit_recorder import WriteUnitRecorder
from .._m145_communication_records import (
    M145CommunicationCreateCommand,
    M145CommunicationRecordState,
    _m145_communication_record_repository,
    create_m145_communication_record,
    mark_m145_communication_record_delivered_to_payer,
    mark_m145_communication_record_locally_completed,
    read_m145_communication_record,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _field_values() -> dict[str, str]:
    return {
        "perceptor.nif": "12345678Z",
        "perceptor.primer-apellido": "Garcia",
        "perceptor.segundo-apellido": "Lopez",
        "perceptor.nombre": "Ana",
        "perceptor.anio-nacimiento": "1981",
    }


def test_mark_m145_communication_record_delivered_to_payer_persists_transition(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        created = create_m145_communication_record(
            M145CommunicationCreateCommand(communication_year=2026, field_values=_field_values()),
            bucket_id=runtime.bucket_id,
        )
        delivered = mark_m145_communication_record_delivered_to_payer(
            created.communication_record_id[:12],
            bucket_id=runtime.bucket_id,
        )
        read_back = read_m145_communication_record(created.communication_record_id, bucket_id=runtime.bucket_id)

    assert delivered.state is M145CommunicationRecordState.DELIVERED_TO_PAYER
    assert delivered.created_at == created.created_at
    assert delivered.delivered_to_payer_at is not None
    assert delivered.delivered_to_payer_at >= created.created_at
    assert delivered.locally_completed_at is None
    assert read_back == delivered


def test_m145_communication_record_transitions_are_idempotent_after_success(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        created = create_m145_communication_record(
            M145CommunicationCreateCommand(communication_year=2026, field_values=_field_values()),
            bucket_id=runtime.bucket_id,
        )
        delivered = mark_m145_communication_record_delivered_to_payer(
            created.communication_record_id,
            bucket_id=runtime.bucket_id,
        )
        delivered_retry = mark_m145_communication_record_delivered_to_payer(
            created.communication_record_id,
            bucket_id=runtime.bucket_id,
        )
        completed = mark_m145_communication_record_locally_completed(
            created.communication_record_id,
            bucket_id=runtime.bucket_id,
        )
        completed_retry = mark_m145_communication_record_locally_completed(
            created.communication_record_id,
            bucket_id=runtime.bucket_id,
        )
        delivered_after_completion = mark_m145_communication_record_delivered_to_payer(
            created.communication_record_id,
            bucket_id=runtime.bucket_id,
        )

    assert delivered_retry == delivered
    assert completed.state is M145CommunicationRecordState.LOCALLY_COMPLETED
    assert completed.delivered_to_payer_at == delivered.delivered_to_payer_at
    assert completed.locally_completed_at is not None
    assert completed.delivered_to_payer_at is not None
    assert completed.locally_completed_at >= completed.delivered_to_payer_at
    assert completed_retry == completed
    assert delivered_after_completion == completed


def test_mark_m145_communication_record_locally_completed_requires_prior_delivery(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        created = create_m145_communication_record(
            M145CommunicationCreateCommand(communication_year=2026, field_values=_field_values()),
            bucket_id=runtime.bucket_id,
        )
        with pytest.raises(ValueError, match="delivered to payer before local completion"):
            mark_m145_communication_record_locally_completed(
                created.communication_record_id,
                bucket_id=runtime.bucket_id,
            )
        read_back = read_m145_communication_record(created.communication_record_id, bucket_id=runtime.bucket_id)

    assert read_back.state is M145CommunicationRecordState.CREATED
    assert read_back.delivered_to_payer_at is None
    assert read_back.locally_completed_at is None


def test_mark_m145_communication_record_delivered_to_payer_requires_valid_record(tmp_path: Path) -> None:
    values = _field_values()
    values.pop("perceptor.nif")

    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        created = create_m145_communication_record(
            M145CommunicationCreateCommand(communication_year=2026, field_values=values),
            bucket_id=runtime.bucket_id,
        )
        with pytest.raises(ValueError, match="validation passes"):
            mark_m145_communication_record_delivered_to_payer(
                created.communication_record_id,
                bucket_id=runtime.bucket_id,
            )
        read_back = read_m145_communication_record(created.communication_record_id, bucket_id=runtime.bucket_id)

    assert read_back.state is M145CommunicationRecordState.CREATED
    assert read_back.delivered_to_payer_at is None
    assert read_back.locally_completed_at is None


def test_communication_creation_commits_record_and_event_in_one_transaction(tmp_path: Path) -> None:
    """Creating a communication record commits it with its history event.

    The transitions saved the record and emitted the event through a separate
    write, so an event-storage failure left the record durable with the history
    showing no transition — an M145 lifecycle change the audit trail cannot
    account for.
    """
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        recorder = WriteUnitRecorder(runtime.repository.engine)

        with recorder.recording():
            create_m145_communication_record(
                M145CommunicationCreateCommand(communication_year=2026, field_values=_field_values()),
                bucket_id=runtime.bucket_id,
            )

        assert recorder.commits_between_writes() == 0


def test_communication_transitions_commit_their_events_in_one_transaction(tmp_path: Path) -> None:
    """Both state transitions commit alongside their events.

    Delivery and local completion carried the same separate-write shape as
    creation, so each is pinned rather than assuming the creation fix covers
    the module.
    """
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        created = create_m145_communication_record(
            M145CommunicationCreateCommand(communication_year=2026, field_values=_field_values()),
            bucket_id=runtime.bucket_id,
        )

        delivery_recorder = WriteUnitRecorder(runtime.repository.engine)
        with delivery_recorder.recording():
            mark_m145_communication_record_delivered_to_payer(
                created.communication_record_id,
                bucket_id=runtime.bucket_id,
            )
        assert delivery_recorder.commits_between_writes() == 0

        completion_recorder = WriteUnitRecorder(runtime.repository.engine)
        with completion_recorder.recording():
            mark_m145_communication_record_locally_completed(
                created.communication_record_id,
                bucket_id=runtime.bucket_id,
            )
        assert completion_recorder.commits_between_writes() == 0


def test_split_communication_write_shape_commits_between_stores(tmp_path: Path) -> None:
    """Anti-tautology: the recorder reports a seam on the shape this replaced.

    Persisting the record and the event catalogue through independent saves —
    the pre-fix sequence — must be observed as more than one transaction, or
    the assertions above could not fail.
    """
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        created = create_m145_communication_record(
            M145CommunicationCreateCommand(communication_year=2026, field_values=_field_values()),
            bucket_id=runtime.bucket_id,
        )
        records = _m145_communication_record_repository(runtime.bucket_id)
        events = BucketEventHistoryRepository()
        catalogue = events.load()
        recorder = WriteUnitRecorder(runtime.repository.engine)

        with recorder.recording():
            records.save(created)
            events.save(catalogue)

        assert recorder.commits_between_writes() >= 1


def test_communication_transitions_persist_their_history_events(tmp_path: Path) -> None:
    """The positive control: the events are really written, not merely co-committed.

    A single-transaction assertion says nothing about whether the event exists;
    without this, dropping the event write entirely would still report zero
    commits between writes.
    """
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        created = create_m145_communication_record(
            M145CommunicationCreateCommand(communication_year=2026, field_values=_field_values()),
            bucket_id=runtime.bucket_id,
        )
        mark_m145_communication_record_delivered_to_payer(
            created.communication_record_id,
            bucket_id=runtime.bucket_id,
        )
        mark_m145_communication_record_locally_completed(
            created.communication_record_id,
            bucket_id=runtime.bucket_id,
        )
        catalogue = BucketEventHistoryRepository().load()

    emitted = {
        event.event_type for event in catalogue.events.values() if event.object_id == created.communication_record_id
    }
    assert BucketEventType.MODELO_145_COMMUNICATION_CREATED in emitted
    assert BucketEventType.MODELO_145_COMMUNICATION_DELIVERED_TO_PAYER in emitted
    assert BucketEventType.MODELO_145_COMMUNICATION_LOCALLY_COMPLETED in emitted
