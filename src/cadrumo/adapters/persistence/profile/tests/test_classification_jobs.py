"""Classification jobs through the real encrypted store and the revision-guarded write path.

A job names the profile's movements and holds typed proposals, so it is stored
only inside an encrypted payload. Every item state survives a round trip, an
update needs the revision it follows, an unknown or another profile's job is
never found, a substituted row is refused, and an unreadable store is reported
as unreadable rather than as an empty queue.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from .....application.ledger.classification_job_repository import (
    ClassificationJobNotFoundError,
    ClassificationJobPersistenceError,
    ClassificationJobRevisionConflictError,
    classification_job_object_key,
)
from .....core.classification.policies import SensitivityClass
from .....core.errors.hierarchy import InternalInvariantError
from .....core.external_constants import UTF_8_ENCODING
from .....core.hashing import sha256_hex
from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .....domain.transactions.classification_job import (
    ClassificationConsentScope,
    ClassificationItemFailureCause,
    ClassificationItemState,
    ClassificationJob,
    ClassificationJobConsent,
    ClassificationJobItem,
    ClassificationJobLane,
    ClassificationJobScope,
    ClassificationJobScopeKind,
    ClassificationJobStatus,
    ClassificationProposal,
)
from .....domain.transactions.enums import BusinessClassification
from .....domain.transactions.errors import ClassificationJobError
from ...storage.secure_object_namespaces import LEDGER_CLASSIFICATION_JOBS_NAMESPACE
from ...storage.sql.secure_objects import SecureObjectRepository
from ..classification_jobs import ClassificationJobRepositoryAdapter
from .secure_objects_fixture import secure_objects

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

__all__ = ["secure_objects"]

_BUCKET_ID = "c5a0e7d2-3b19-4f84-8e6a-1d2f9b7c4a03"
_OTHER_BUCKET_ID = "2f9e4b71-8c05-4d3a-b6e2-7a1c0d5f8e96"


@pytest.fixture
def bucket_id() -> str:
    return _BUCKET_ID


_AT = datetime(filing_year_envelope().horizon, 4, 2, 9, 0, tzinfo=UTC)
_LATER = _AT + timedelta(minutes=5)
_MODEL = "synthetic-hosted-model"
_CONSENT_REFERENCE = "consent-synthetic-grant"


def _movement(label: str) -> str:
    return sha256_hex(f"synthetic movement {label}".encode())


def _proposal(revision: str) -> ClassificationProposal:
    return ClassificationProposal(
        movement_revision_id=revision,
        classification=BusinessClassification.MIXED,
        confidence=Decimal("0.73"),
        category="synthetic_category",
        iva_category="synthetic_iva",
        business_pct=Decimal("0.4"),
        multiple_components=False,
        provenance="llm:local-text:synthetic-model",
        proposed_at=_LATER,
    )


def _job(*, bucket: str = _BUCKET_ID, labels: tuple[str, ...] = ("a", "b"), off_host: bool = True) -> ClassificationJob:
    return ClassificationJob.enqueue(
        bucket_id=bucket,
        scope=ClassificationJobScope(
            kind=ClassificationJobScopeKind.PERIOD,
            period_start=date(filing_year_envelope().horizon, 1, 1),
            period_end=date(filing_year_envelope().horizon, 3, 31),
        ),
        movement_ids=tuple(_movement(label) for label in labels),
        lane=ClassificationJobLane(
            provider_id="hosted", transport="api", model=_MODEL, effort="medium", reads_off_host=off_host
        ),
        consent=(
            ClassificationJobConsent(
                scope=ClassificationConsentScope.AGENT_SESSION, consent_reference=_CONSENT_REFERENCE, granted_at=_AT
            )
            if off_host
            else None
        ),
        at=_AT,
    )


def _repository(objects: SecureObjectRepository, bucket: str = _BUCKET_ID) -> ClassificationJobRepositoryAdapter:
    return ClassificationJobRepositoryAdapter(objects=objects, bucket_id=bucket)


def _stored_row(
    objects: SecureObjectRepository, job: ClassificationJob
) -> tuple[str, bytes, int, datetime, SensitivityClass]:
    key = classification_job_object_key(bucket_id=job.bucket_id, job_id=job.job_id)
    stored = objects.load(
        LEDGER_CLASSIFICATION_JOBS_NAMESPACE.namespace,
        key,
        expected_class=LEDGER_CLASSIFICATION_JOBS_NAMESPACE.sensitivity,
        max_supported_version=LEDGER_CLASSIFICATION_JOBS_NAMESPACE.schema_version,
    )
    assert stored is not None
    return key, stored.payload, stored.schema_version, stored.written_at, stored.classification


def test_a_created_job_round_trips_and_its_fields_are_never_plaintext(
    tmp_path: Path, secure_objects: SecureObjectRepository
) -> None:
    repository = _repository(secure_objects)
    job = _job()

    repository.create(job)

    assert repository.get(job.job_id) == job
    assert repository.list_jobs() == (job,)
    on_disk = b"".join(path.read_bytes() for path in tmp_path.rglob("*") if path.is_file())
    for secret in (_MODEL, _CONSENT_REFERENCE, _movement("a"), job.job_id):
        assert secret.encode(UTF_8_ENCODING) not in on_disk


def test_every_item_and_job_state_survives_the_encrypted_round_trip(secure_objects: SecureObjectRepository) -> None:
    repository = _repository(secure_objects)
    labels = ("pending", "proposed", "failed", "unknown", "stale", "cancelled", "running")
    job = _job(labels=labels)
    repository.create(job)

    def running(item: ClassificationJobItem) -> ClassificationJobItem:
        return item.transitioned(ClassificationItemState.RUNNING)

    pending, proposed, failed, unknown, stale, cancelled, in_flight = job.items
    started = job.successor(
        at=_LATER,
        status=ClassificationJobStatus.RUNNING,
        items=(
            pending,
            running(proposed),
            running(failed),
            running(unknown),
            running(stale),
            running(cancelled),
            running(in_flight),
        ),
    )
    repository.update(started)
    _, s_proposed, s_failed, s_unknown, s_stale, s_cancelled, s_in_flight = started.items
    progressed = started.successor(
        at=_LATER,
        items=(
            pending,
            s_proposed.transitioned(ClassificationItemState.PROPOSED, proposal=_proposal("rev-proposed")),
            s_failed.transitioned(
                ClassificationItemState.FAILED, failure_cause=ClassificationItemFailureCause.MODEL_UNAVAILABLE
            ),
            s_unknown.transitioned(ClassificationItemState.UNKNOWN),
            s_stale.transitioned(ClassificationItemState.PROPOSED, proposal=_proposal("rev-old")),
            s_cancelled.transitioned(ClassificationItemState.CANCELLED),
            s_in_flight,
        ),
    )
    repository.update(progressed)
    assert repository.get(job.job_id) == progressed
    staled = progressed.successor(
        at=_LATER,
        items=(
            *progressed.items[:4],
            progressed.items[4].transitioned(ClassificationItemState.STALE),
            *progressed.items[5:],
        ),
    )
    repository.update(staled)

    stored = repository.get(job.job_id)
    assert stored == staled
    assert stored.revision == 4
    assert [item.state for item in stored.items] == [
        ClassificationItemState.PENDING,
        ClassificationItemState.PROPOSED,
        ClassificationItemState.FAILED,
        ClassificationItemState.UNKNOWN,
        ClassificationItemState.STALE,
        ClassificationItemState.CANCELLED,
        ClassificationItemState.RUNNING,
    ]
    assert stored.items[2].failure_cause is ClassificationItemFailureCause.MODEL_UNAVAILABLE
    assert stored.items[4].proposal == _proposal("rev-old")

    statuses = [stored.status]
    interrupted = stored.successor(
        at=_LATER,
        status=ClassificationJobStatus.INTERRUPTED,
        items=(*stored.items[:-1], stored.items[-1].transitioned(ClassificationItemState.UNKNOWN)),
    )
    repository.update(interrupted)
    statuses.append(repository.get(job.job_id).status)
    queued = interrupted.successor(at=_LATER, status=ClassificationJobStatus.QUEUED)
    repository.update(queued)
    statuses.append(repository.get(job.job_id).status)
    cancelled_job = queued.successor(
        at=_LATER,
        status=ClassificationJobStatus.CANCELLED,
        items=tuple(
            item.transitioned(ClassificationItemState.CANCELLED)
            if item.state in {ClassificationItemState.PENDING, ClassificationItemState.UNKNOWN}
            else item
            for item in queued.items
        ),
    )
    repository.update(cancelled_job)
    statuses.append(repository.get(job.job_id).status)
    repository.update(cancelled_job.successor(at=_LATER, status=ClassificationJobStatus.DISMISSED))
    statuses.append(repository.get(job.job_id).status)
    assert statuses == [
        ClassificationJobStatus.RUNNING,
        ClassificationJobStatus.INTERRUPTED,
        ClassificationJobStatus.QUEUED,
        ClassificationJobStatus.CANCELLED,
        ClassificationJobStatus.DISMISSED,
    ]
    assert repository.get(job.job_id).revision == 8


def test_settled_and_cancelling_states_round_trip(secure_objects: SecureObjectRepository) -> None:
    repository = _repository(secure_objects)
    job = _job(labels=("a",), off_host=False)
    repository.create(job)
    running = job.successor(
        at=_LATER,
        status=ClassificationJobStatus.RUNNING,
        items=(job.items[0].transitioned(ClassificationItemState.RUNNING),),
    )
    repository.update(running)
    cancelling = running.successor(at=_LATER, status=ClassificationJobStatus.CANCELLING)
    repository.update(cancelling)
    assert repository.get(job.job_id).status is ClassificationJobStatus.CANCELLING
    assert repository.get(job.job_id).consent is None

    other = _job(labels=("b",), off_host=False)
    repository.create(other)
    other_running = other.successor(
        at=_LATER,
        status=ClassificationJobStatus.RUNNING,
        items=(other.items[0].transitioned(ClassificationItemState.RUNNING),),
    )
    repository.update(other_running)
    settled = other_running.successor(
        at=_LATER,
        status=ClassificationJobStatus.SETTLED,
        items=(other_running.items[0].transitioned(ClassificationItemState.PROPOSED, proposal=_proposal("rev-b")),),
    )
    repository.update(settled)
    assert repository.get(other.job_id) == settled
    assert {stored.job_id for stored in repository.list_jobs()} == {job.job_id, other.job_id}


def test_an_update_needs_the_revision_it_follows(secure_objects: SecureObjectRepository) -> None:
    repository = _repository(secure_objects)
    job = _job()
    repository.create(job)
    first = job.successor(at=_LATER, status=ClassificationJobStatus.CANCELLED, items=_cancelled_items(job))
    rival = job.successor(at=_LATER, status=ClassificationJobStatus.RUNNING, items=_started_items(job))

    repository.update(first)
    with pytest.raises(ClassificationJobRevisionConflictError):
        repository.update(rival)
    with pytest.raises(ClassificationJobRevisionConflictError):
        repository.update(first)
    assert repository.get(job.job_id) == first


def test_an_update_that_does_not_follow_the_stored_job_is_refused(secure_objects: SecureObjectRepository) -> None:
    repository = _repository(secure_objects)
    job = _job()
    repository.create(job)
    forged = job.successor(at=_LATER, status=ClassificationJobStatus.RUNNING, items=_started_items(job)).model_copy(
        update={"lane": job.lane.model_copy(update={"model": "another-model"})}
    )

    with pytest.raises(ClassificationJobError, match="never change"):
        repository.update(forged)
    assert repository.get(job.job_id) == job


def test_creating_an_existing_job_is_a_conflict_and_a_new_job_starts_at_revision_one(
    secure_objects: SecureObjectRepository,
) -> None:
    repository = _repository(secure_objects)
    job = _job()
    repository.create(job)

    with pytest.raises(ClassificationJobRevisionConflictError):
        repository.create(job)
    advanced = job.successor(at=_LATER, status=ClassificationJobStatus.RUNNING, items=_started_items(job))
    with pytest.raises(ClassificationJobError, match="revision 1"):
        repository.create(advanced.model_copy(update={"job_id": sha256_hex(b"synthetic other job")}))


def test_an_unknown_job_is_not_found(secure_objects: SecureObjectRepository) -> None:
    repository = _repository(secure_objects)
    job = _job()

    with pytest.raises(ClassificationJobNotFoundError):
        repository.get(job.job_id)
    with pytest.raises(ClassificationJobNotFoundError):
        repository.get("../not-a-job")
    with pytest.raises(ClassificationJobNotFoundError):
        repository.update(job.successor(at=_LATER, status=ClassificationJobStatus.RUNNING, items=_started_items(job)))
    assert repository.list_jobs() == ()


def test_another_profiles_job_is_never_read_or_written_through_this_profile(
    secure_objects: SecureObjectRepository,
) -> None:
    repository = _repository(secure_objects)
    foreign = _job(bucket=_OTHER_BUCKET_ID)

    with pytest.raises(InternalInvariantError):
        repository.create(foreign)
    with pytest.raises(InternalInvariantError):
        repository.update(
            foreign.successor(at=_LATER, status=ClassificationJobStatus.RUNNING, items=_started_items(foreign))
        )

    # A repository bound to the other bucket over this store addresses that bucket's keys only.
    other = _repository(secure_objects, _OTHER_BUCKET_ID)
    other.create(foreign)
    with pytest.raises(ClassificationJobNotFoundError):
        repository.get(foreign.job_id)
    with pytest.raises(ClassificationJobPersistenceError):
        repository.list_jobs()


def test_a_row_stored_under_another_jobs_key_is_refused(secure_objects: SecureObjectRepository) -> None:
    repository = _repository(secure_objects)
    original = _job(labels=("a",))
    other = _job(labels=("b",))
    repository.create(original)
    _key, payload, schema_version, written_at, classification = _stored_row(secure_objects, original)

    secure_objects.save(
        namespace=LEDGER_CLASSIFICATION_JOBS_NAMESPACE.namespace,
        object_key=classification_job_object_key(bucket_id=_BUCKET_ID, job_id=other.job_id),
        classification=classification,
        schema_version=schema_version,
        written_at=written_at,
        payload=payload,
    )

    with pytest.raises(ClassificationJobPersistenceError):
        repository.get(other.job_id)
    with pytest.raises(ClassificationJobPersistenceError):
        repository.list_jobs()


def test_an_unreadable_store_is_reported_and_never_an_empty_queue(secure_objects: SecureObjectRepository) -> None:
    repository = _repository(secure_objects)
    job = _job()
    repository.create(job)
    key, payload, schema_version, written_at, classification = _stored_row(secure_objects, job)
    broken = json.loads(payload)
    broken["payload"]["status"] = "no-such-status"
    secure_objects.save(
        namespace=LEDGER_CLASSIFICATION_JOBS_NAMESPACE.namespace,
        object_key=key,
        classification=classification,
        schema_version=schema_version,
        written_at=written_at,
        payload=json.dumps(broken).encode(UTF_8_ENCODING),
    )

    with pytest.raises(ClassificationJobPersistenceError):
        repository.list_jobs()
    with pytest.raises(ClassificationJobPersistenceError):
        repository.get(job.job_id)


def _started_items(job: ClassificationJob) -> tuple[ClassificationJobItem, ...]:
    return (job.items[0].transitioned(ClassificationItemState.RUNNING), *job.items[1:])


def _cancelled_items(job: ClassificationJob) -> tuple[ClassificationJobItem, ...]:
    return tuple(item.transitioned(ClassificationItemState.CANCELLED) for item in job.items)
