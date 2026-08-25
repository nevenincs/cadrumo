"""Real-behavior tests for the shared snapshot lifecycle base."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, override

import pytest
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ....adapters.persistence.profile.snapshots import SecureSnapshotRepository
from ....adapters.persistence.storage import (
    TEST_SNAPSHOT_BASE_PROBE_NAMESPACE,
    Envelope,
    SensitivityClass,
)
from ....adapters.persistence.storage.sql import SecureObjectRecord, SecureObjectRepository
from ....core.errors import CadrumoError
from ....core.hashing import content_hash_hex
from ....core.identity import BucketId
from ..borrador_100 import Borrador100SnapshotRepository, BorradorSnapshotNotFoundError
from ..errors import LiveApplicationInputError
from ..snapshot_base import (
    SnapshotLifecycleState,
    SnapshotNotFoundError,
    SnapshotRepository,
    SnapshotService,
    SnapshotStateFilter,
    enforce_snapshot_state_invariants,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_PROBE_NAMESPACE = "cadrumo.application.live.test_snapshot_base_probe"
_PROBE_VERSION = 1
_BUCKET_ID = "52525252-5252-4252-8252-525252525252"
_OTHER_BUCKET_ID = "53535353-5353-4353-8353-535353535353"
_PROTO_BUCKET_ID = "54545454-5454-4454-8454-545454545454"


# ---- Test payload ---------------------------------------------------------


class ProbeSnapshot(BaseModel):
    """Minimal payload exercising the shared lifecycle invariants."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    snapshot_id: str = Field(min_length=1, max_length=128)
    bucket_id: BucketId
    axis_label: str = Field(min_length=1, max_length=64)
    captured_at: datetime
    payload_text: str
    state: SnapshotLifecycleState
    superseded_by_snapshot_id: str | None = Field(default=None, min_length=1, max_length=128)
    discarded_at: datetime | None = None
    discarded_by: str = Field(default="", max_length=128)
    discard_reason: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def _enforce_state(self) -> ProbeSnapshot:
        enforce_snapshot_state_invariants(
            state=self.state,
            has_supersession_pointer=self.superseded_by_snapshot_id is not None,
            discarded_at=self.discarded_at,
            discarded_by=self.discarded_by,
            discard_reason=self.discard_reason,
        )
        return self


class _ProbeCaptureRequest(BaseModel):
    """Typed capture input for the lifecycle-service probe."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    axis_label: str = Field(min_length=1, max_length=64)
    captured_at: datetime
    payload_text: str


def _probe_object_key(bucket_id: str, snapshot_id: str) -> str:
    return f"snapshot-base-probe:{bucket_id}:{snapshot_id}"


def _probe_from_record(record: SecureObjectRecord) -> ProbeSnapshot:
    envelope = Envelope[ProbeSnapshot].model_validate_json(record.payload.decode("utf-8"))
    return envelope.payload


# ---- Test repository ------------------------------------------------------


class ProbeRepository:
    """SecureObjectRepository-backed repository satisfying SnapshotRepository[ProbeSnapshot]."""

    def __init__(self, *, bucket_id: str, objects: SecureObjectRepository) -> None:
        self._bucket_id = bucket_id.strip()
        if not self._bucket_id:
            raise LiveApplicationInputError("bucket_id must not be blank")
        self._objects = objects

    @property
    def bucket_id(self) -> str:
        return self._bucket_id

    def exists(self, snapshot_id: str) -> bool:
        return self._objects.exists(_PROBE_NAMESPACE, _probe_object_key(self._bucket_id, snapshot_id))

    def load(self, snapshot_id: str) -> ProbeSnapshot:
        record = self._objects.load(
            _PROBE_NAMESPACE,
            _probe_object_key(self._bucket_id, snapshot_id),
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_PROBE_VERSION,
        )
        if record is None:
            raise LiveApplicationInputError(f"probe snapshot {snapshot_id!r} not found")
        return _probe_from_record(record)

    def list_snapshots(self) -> tuple[ProbeSnapshot, ...]:
        snapshots = [
            _probe_from_record(record)
            for record in self._objects.list_records(
                _PROBE_NAMESPACE,
                expected_class=SensitivityClass.FINANCIAL,
                max_supported_version=_PROBE_VERSION,
            )
        ]
        bucket_snapshots = [snapshot for snapshot in snapshots if snapshot.bucket_id == self._bucket_id]
        return tuple(sorted(bucket_snapshots, key=lambda s: (s.captured_at, s.snapshot_id)))

    def resolve(self, snapshot_id: str) -> ProbeSnapshot:
        trimmed = snapshot_id.strip()
        if not trimmed:
            raise LiveApplicationInputError("snapshot_id must not be blank")
        matches = [
            snapshot
            for snapshot in self.list_snapshots()
            if snapshot.snapshot_id == trimmed or snapshot.snapshot_id.startswith(trimmed)
        ]
        if not matches:
            raise LiveApplicationInputError(f"probe snapshot {snapshot_id!r} not found")
        if len(matches) > 1:
            raise LiveApplicationInputError(f"probe snapshot prefix {snapshot_id!r} is ambiguous")
        return matches[0]

    def save(self, snapshot: ProbeSnapshot) -> None:
        envelope = Envelope[ProbeSnapshot](
            schema_version=_PROBE_VERSION,
            written_at=snapshot.captured_at,
            classification=SensitivityClass.FINANCIAL,
            payload=snapshot,
        )
        self._objects.save(
            namespace=_PROBE_NAMESPACE,
            object_key=_probe_object_key(self._bucket_id, snapshot.snapshot_id),
            classification=SensitivityClass.FINANCIAL,
            schema_version=_PROBE_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )


# ---- Test service ---------------------------------------------------------


class ProbeService(SnapshotService[ProbeSnapshot, _ProbeCaptureRequest]):
    def __init__(self, *, bucket_id: str, repository: ProbeRepository) -> None:
        super().__init__(bucket_id=bucket_id, repository=repository)

    def capture(self, *, axis_label: str, captured_at: datetime, payload_text: str) -> ProbeSnapshot:
        return self._capture_with_lifecycle(
            _ProbeCaptureRequest(
                axis_label=axis_label,
                captured_at=captured_at,
                payload_text=payload_text,
            ),
        )

    @override
    def _derive_snapshot_id(self, capture: _ProbeCaptureRequest) -> str:
        return content_hash_hex(
            {
                "axis_label": capture.axis_label,
                "captured_at": capture.captured_at.isoformat(),
                "payload_text": capture.payload_text,
            },
        )

    @override
    def _build_active_payload(self, *, snapshot_id: str, capture: _ProbeCaptureRequest) -> ProbeSnapshot:
        return ProbeSnapshot(
            snapshot_id=snapshot_id,
            bucket_id=self._repository.bucket_id,
            axis_label=capture.axis_label,
            captured_at=capture.captured_at,
            payload_text=capture.payload_text,
            state=SnapshotLifecycleState.ACTIVE,
        )

    @override
    def _payload_axis_key(self, payload: ProbeSnapshot) -> tuple[Any, ...]:
        return (payload.axis_label,)

    @override
    def _payload_captured_at(self, payload: ProbeSnapshot) -> datetime:
        return payload.captured_at

    @override
    def _payload_snapshot_id(self, payload: ProbeSnapshot) -> str:
        return payload.snapshot_id

    @override
    def _payload_state(self, payload: ProbeSnapshot) -> SnapshotLifecycleState:
        return payload.state

    @override
    def _demote_to_superseded(self, payload: ProbeSnapshot, *, superseded_by: str) -> ProbeSnapshot:
        return payload.model_copy(
            update={
                "state": SnapshotLifecycleState.SUPERSEDED,
                "superseded_by_snapshot_id": superseded_by,
            },
        )


_CAPTURED_AT = datetime(2026, 4, 3, 10, 0, tzinfo=UTC)


# ---- Lifecycle invariant tests -------------------------------------------


def test_active_snapshot_rejects_supersession_pointer() -> None:
    with pytest.raises(LiveApplicationInputError) as excinfo:
        enforce_snapshot_state_invariants(
            state=SnapshotLifecycleState.ACTIVE,
            has_supersession_pointer=True,
            discarded_at=None,
            discarded_by="",
        )

    key = "application.live.snapshot_base.errors.state_active_supersession_pointer"
    assert excinfo.value.translated_message == key
    assert excinfo.value.context == {"state": "active", "has_supersession_pointer": True}
    assert str(excinfo.value) == key


def test_active_snapshot_rejects_discard_metadata() -> None:
    with pytest.raises(LiveApplicationInputError) as excinfo:
        enforce_snapshot_state_invariants(
            state=SnapshotLifecycleState.ACTIVE,
            has_supersession_pointer=False,
            discarded_at=_CAPTURED_AT,
            discarded_by="operator",
        )

    key = "application.live.snapshot_base.errors.state_discard_metadata_forbidden"
    assert excinfo.value.translated_message == key
    assert str(excinfo.value) == key


def test_superseded_snapshot_requires_pointer() -> None:
    key = "application.live.snapshot_base.errors.state_supersession_pointer_required"
    with pytest.raises(LiveApplicationInputError, match=key):
        enforce_snapshot_state_invariants(
            state=SnapshotLifecycleState.SUPERSEDED,
            has_supersession_pointer=False,
            discarded_at=None,
            discarded_by="",
        )


def test_superseded_snapshot_rejects_discard_metadata() -> None:
    key = "application.live.snapshot_base.errors.state_discard_metadata_forbidden"
    with pytest.raises(LiveApplicationInputError, match=key):
        enforce_snapshot_state_invariants(
            state=SnapshotLifecycleState.SUPERSEDED,
            has_supersession_pointer=True,
            discarded_at=None,
            discarded_by="",
            discard_reason="audit-only",
        )


def test_discarded_snapshot_requires_actor_and_timestamp() -> None:
    key = "application.live.snapshot_base.errors.state_discard_audit_required"
    with pytest.raises(LiveApplicationInputError, match=key):
        enforce_snapshot_state_invariants(
            state=SnapshotLifecycleState.DISCARDED,
            has_supersession_pointer=False,
            discarded_at=None,
            discarded_by="",
        )


def test_discarded_snapshot_rejects_supersession_pointer() -> None:
    key = "application.live.snapshot_base.errors.state_discarded_supersession_pointer"
    with pytest.raises(LiveApplicationInputError, match=key):
        enforce_snapshot_state_invariants(
            state=SnapshotLifecycleState.DISCARDED,
            has_supersession_pointer=True,
            discarded_at=_CAPTURED_AT,
            discarded_by="operator",
        )


def test_active_snapshot_passes_with_no_pointers_or_audit() -> None:
    enforce_snapshot_state_invariants(
        state=SnapshotLifecycleState.ACTIVE,
        has_supersession_pointer=False,
        discarded_at=None,
        discarded_by="",
    )


# ---- SnapshotService roundtrip tests -------------------------------------


def test_service_capture_persists_active_snapshot(secure_objects: SecureObjectRepository) -> None:
    repository = ProbeRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    service = ProbeService(bucket_id=_BUCKET_ID, repository=repository)

    snapshot = service.capture(axis_label="renta-2025", captured_at=_CAPTURED_AT, payload_text="alpha")

    assert snapshot.state is SnapshotLifecycleState.ACTIVE
    assert snapshot.superseded_by_snapshot_id is None
    assert repository.load(snapshot.snapshot_id) == snapshot


def test_service_capture_deduplicates_by_content_id(secure_objects: SecureObjectRepository) -> None:
    repository = ProbeRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    service = ProbeService(bucket_id=_BUCKET_ID, repository=repository)

    first = service.capture(axis_label="renta-2025", captured_at=_CAPTURED_AT, payload_text="alpha")
    second = service.capture(axis_label="renta-2025", captured_at=_CAPTURED_AT, payload_text="alpha")

    assert first == second
    assert len(repository.list_snapshots()) == 1


def test_service_capture_supersedes_prior_active_on_same_axis(
    secure_objects: SecureObjectRepository,
) -> None:
    repository = ProbeRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    service = ProbeService(bucket_id=_BUCKET_ID, repository=repository)

    first = service.capture(axis_label="renta-2025", captured_at=_CAPTURED_AT, payload_text="alpha")
    second = service.capture(
        axis_label="renta-2025",
        captured_at=_CAPTURED_AT + timedelta(hours=1),
        payload_text="beta",
    )

    snapshots = repository.list_snapshots()
    assert len(snapshots) == 2
    second_loaded = repository.load(second.snapshot_id)
    first_loaded = repository.load(first.snapshot_id)
    assert second_loaded.state is SnapshotLifecycleState.ACTIVE
    assert first_loaded.state is SnapshotLifecycleState.SUPERSEDED
    assert first_loaded.superseded_by_snapshot_id == second.snapshot_id


def test_service_capture_demotes_late_arrival(secure_objects: SecureObjectRepository) -> None:
    repository = ProbeRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    service = ProbeService(bucket_id=_BUCKET_ID, repository=repository)

    newer = service.capture(
        axis_label="renta-2025",
        captured_at=_CAPTURED_AT + timedelta(hours=1),
        payload_text="beta",
    )
    older = service.capture(axis_label="renta-2025", captured_at=_CAPTURED_AT, payload_text="alpha")

    older_loaded = repository.load(older.snapshot_id)
    newer_loaded = repository.load(newer.snapshot_id)
    assert newer_loaded.state is SnapshotLifecycleState.ACTIVE
    assert older_loaded.state is SnapshotLifecycleState.SUPERSEDED
    assert older_loaded.superseded_by_snapshot_id == newer.snapshot_id


def test_service_capture_does_not_supersede_across_axis(
    secure_objects: SecureObjectRepository,
) -> None:
    repository = ProbeRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    service = ProbeService(bucket_id=_BUCKET_ID, repository=repository)

    first = service.capture(axis_label="renta-2025", captured_at=_CAPTURED_AT, payload_text="alpha")
    second = service.capture(
        axis_label="renta-2026",
        captured_at=_CAPTURED_AT + timedelta(hours=1),
        payload_text="beta",
    )

    assert repository.load(first.snapshot_id).state is SnapshotLifecycleState.ACTIVE
    assert repository.load(second.snapshot_id).state is SnapshotLifecycleState.ACTIVE


def test_service_resolve_snapshot_supports_prefix(secure_objects: SecureObjectRepository) -> None:
    repository = ProbeRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    service = ProbeService(bucket_id=_BUCKET_ID, repository=repository)

    captured = service.capture(axis_label="renta-2025", captured_at=_CAPTURED_AT, payload_text="alpha")
    resolved = service.resolve_snapshot(captured.snapshot_id[:12])
    assert resolved == captured


def test_service_constructor_rejects_bucket_mismatch(secure_objects: SecureObjectRepository) -> None:
    repository = ProbeRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    with pytest.raises(LiveApplicationInputError) as excinfo:
        ProbeService(bucket_id=_OTHER_BUCKET_ID, repository=repository)

    key = "application.live.snapshot_base.errors.service_bucket_mismatch"
    assert excinfo.value.translated_message == key
    assert excinfo.value.context == {
        "requested_bucket_id": _OTHER_BUCKET_ID,
        "repository_bucket_id": _BUCKET_ID,
    }
    assert str(excinfo.value) == key


# ---- Per-service SnapshotNotFoundError subclass hierarchy ---------------


def test_borrador_snapshot_not_found_error_inherits_shared_base() -> None:
    error = BorradorSnapshotNotFoundError("borrador snapshot 'x' not found")
    assert isinstance(error, SnapshotNotFoundError)
    assert isinstance(error, CadrumoError)
    assert issubclass(BorradorSnapshotNotFoundError, SnapshotNotFoundError)
    assert issubclass(BorradorSnapshotNotFoundError, CadrumoError)


def test_borrador_snapshot_not_found_error_accepts_structured_kwargs() -> None:
    # CadrumoError-first MRO means the structured kwargs reach CadrumoError at
    # all: KeyError.__init__ rejects every keyword, so an MRO that put KeyError
    # first would raise TypeError here rather than fail somewhere subtler.
    #
    # This asserted the same property through suggestion= until that transport
    # was deleted. The kwarg was only ever the vehicle -- the property is the
    # MRO -- so it is re-expressed through the surviving structured kwargs
    # rather than dropped, which would have retired a real capability check
    # along with the evidence that it was ever made.
    error = BorradorSnapshotNotFoundError(
        f"borrador snapshot 'abc' not found in bucket {_BUCKET_ID!r}",
        context={"snapshot_id": "abc"},
        translated_message="application.live.borrador.errors.snapshot_not_found",
    )
    assert error.context == {"snapshot_id": "abc"}
    assert error.translated_message == "application.live.borrador.errors.snapshot_not_found"
    mro = SnapshotNotFoundError.__mro__
    assert mro.index(CadrumoError) < mro.index(KeyError)


# ---- SnapshotRepository structural-conformance gate (contract) -----------------
# Rule 9-A: conformance is STRUCTURAL (isinstance against the @runtime_checkable
# Protocol), NOT explicit inheritance. Concrete repos must NOT inherit from
# SnapshotRepository — the isinstance check verifies structural conformance.


def test_borrador100_snapshot_repository_conforms_to_protocol(
    secure_objects: SecureObjectRepository,
) -> None:
    """Borrador100SnapshotRepository satisfies SnapshotRepository[…] structurally."""
    repo = Borrador100SnapshotRepository(bucket_id=_PROTO_BUCKET_ID, objects=secure_objects)
    assert isinstance(repo, SnapshotRepository)
    # Rule 9-A: structural conformance only — no explicit inheritance.
    assert SnapshotRepository not in type(repo).__mro__


def test_secure_snapshot_repository_conforms_to_protocol(
    secure_objects: SecureObjectRepository,
) -> None:
    """SecureSnapshotRepository satisfies SnapshotRepository[…] structurally.

    Uses the expedientes namespace+model to exercise the generic class.
    """
    from ....adapters.persistence.storage import LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE
    from ..expedientes import (
        PersistedExpedientesSnapshot,
        expedientes_snapshot_object_key,
    )

    repo: SecureSnapshotRepository[PersistedExpedientesSnapshot] = SecureSnapshotRepository(
        bucket_id=_PROTO_BUCKET_ID,
        payload_model=PersistedExpedientesSnapshot,
        namespace_definition=LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE,
        object_key=expedientes_snapshot_object_key,
        not_found_factory=lambda sid: KeyError(sid),
        ambiguous_prefix_factory=lambda sid, ids: KeyError(sid),
        domain_label="expedientes",
        input_error_cls=LiveApplicationInputError,
        objects=secure_objects,
    )
    assert isinstance(repo, SnapshotRepository)


def test_secure_snapshot_repository_list_rejects_payload_bucket_mismatch(
    secure_objects: SecureObjectRepository,
) -> None:
    snapshot = ProbeSnapshot(
        snapshot_id="misrouted-snapshot",
        bucket_id=_OTHER_BUCKET_ID,
        axis_label="renta-2025",
        captured_at=_CAPTURED_AT,
        payload_text="misrouted",
        state=SnapshotLifecycleState.ACTIVE,
    )
    envelope = Envelope[ProbeSnapshot](
        schema_version=TEST_SNAPSHOT_BASE_PROBE_NAMESPACE.schema_version,
        written_at=_CAPTURED_AT,
        classification=TEST_SNAPSHOT_BASE_PROBE_NAMESPACE.sensitivity,
        payload=snapshot,
    )
    secure_objects.save(
        namespace=TEST_SNAPSHOT_BASE_PROBE_NAMESPACE.namespace,
        object_key=_probe_object_key(_BUCKET_ID, snapshot.snapshot_id),
        classification=TEST_SNAPSHOT_BASE_PROBE_NAMESPACE.sensitivity,
        schema_version=TEST_SNAPSHOT_BASE_PROBE_NAMESPACE.schema_version,
        written_at=envelope.written_at,
        payload=envelope.model_dump_json().encode("utf-8"),
    )
    repo: SecureSnapshotRepository[ProbeSnapshot] = SecureSnapshotRepository(
        bucket_id=_BUCKET_ID,
        payload_model=ProbeSnapshot,
        namespace_definition=TEST_SNAPSHOT_BASE_PROBE_NAMESPACE,
        object_key=_probe_object_key,
        not_found_factory=lambda sid: LiveApplicationInputError(f"probe snapshot {sid!r} not found"),
        ambiguous_prefix_factory=lambda sid, ids: LiveApplicationInputError(
            f"probe snapshot prefix {sid!r} is ambiguous",
        ),
        domain_label="probe",
        input_error_cls=LiveApplicationInputError,
        objects=secure_objects,
    )

    with pytest.raises(LiveApplicationInputError) as exc_info:
        repo.list_snapshots()

    assert exc_info.value.translated_message == "application.live.snapshot_base.errors.snapshot_bucket_mismatch"
    assert exc_info.value.context == {
        "domain_label": "probe",
        "snapshot_bucket": _OTHER_BUCKET_ID,
        "repository_bucket": _BUCKET_ID,
    }


def _probe_secure_repository(secure_objects: SecureObjectRepository) -> SecureSnapshotRepository[ProbeSnapshot]:
    """Return a :class:`SecureSnapshotRepository` bound to the probe payload and bucket."""
    return SecureSnapshotRepository(
        bucket_id=_BUCKET_ID,
        payload_model=ProbeSnapshot,
        namespace_definition=TEST_SNAPSHOT_BASE_PROBE_NAMESPACE,
        object_key=_probe_object_key,
        not_found_factory=lambda sid: LiveApplicationInputError(f"probe snapshot {sid!r} not found"),
        ambiguous_prefix_factory=lambda sid, ids: LiveApplicationInputError(
            f"probe snapshot prefix {sid!r} is ambiguous",
        ),
        domain_label="probe",
        input_error_cls=LiveApplicationInputError,
        objects=secure_objects,
    )


def _save_probe_under_key(
    secure_objects: SecureObjectRepository,
    snapshot: ProbeSnapshot,
    *,
    object_key_snapshot_id: str,
) -> None:
    """Persist a valid ``snapshot`` envelope under ``object_key_snapshot_id``'s row key."""
    envelope = Envelope[ProbeSnapshot](
        schema_version=TEST_SNAPSHOT_BASE_PROBE_NAMESPACE.schema_version,
        written_at=_CAPTURED_AT,
        classification=TEST_SNAPSHOT_BASE_PROBE_NAMESPACE.sensitivity,
        payload=snapshot,
    )
    secure_objects.save(
        namespace=TEST_SNAPSHOT_BASE_PROBE_NAMESPACE.namespace,
        object_key=_probe_object_key(_BUCKET_ID, object_key_snapshot_id),
        classification=TEST_SNAPSHOT_BASE_PROBE_NAMESPACE.sensitivity,
        schema_version=TEST_SNAPSHOT_BASE_PROBE_NAMESPACE.schema_version,
        written_at=envelope.written_at,
        payload=envelope.model_dump_json().encode("utf-8"),
    )


def _probe_snapshot(snapshot_id: str) -> ProbeSnapshot:
    return ProbeSnapshot(
        snapshot_id=snapshot_id,
        bucket_id=_BUCKET_ID,
        axis_label="renta-2025",
        captured_at=_CAPTURED_AT,
        payload_text="body",
        state=SnapshotLifecycleState.ACTIVE,
    )


def test_secure_snapshot_repository_list_returns_a_snapshot_under_its_own_key(
    secure_objects: SecureObjectRepository,
) -> None:
    snapshot = _probe_snapshot("snapshot-a")
    _save_probe_under_key(secure_objects, snapshot, object_key_snapshot_id="snapshot-a")

    assert _probe_secure_repository(secure_objects).list_snapshots() == (snapshot,)


def test_secure_snapshot_repository_list_rejects_a_snapshot_under_a_foreign_key(
    secure_objects: SecureObjectRepository,
) -> None:
    """A valid snapshot re-encrypted under another snapshot's key must not enumerate.

    ``load`` already refused this row; before the list path re-addressed each
    record, enumeration returned it and every ``latest``/``resolve`` consumer
    built on enumeration surfaced the foreign snapshot identity.
    """
    foreign = _probe_snapshot("snapshot-b")
    _save_probe_under_key(secure_objects, foreign, object_key_snapshot_id="snapshot-a")
    repo = _probe_secure_repository(secure_objects)

    with pytest.raises(LiveApplicationInputError) as exc_info:
        repo.list_snapshots()

    assert exc_info.value.translated_message == "application.live.snapshot_base.errors.snapshot_key_mismatch"
    assert exc_info.value.context == {
        "domain_label": "probe",
        "snapshot_id": "snapshot-b",
        "repository_bucket": _BUCKET_ID,
    }


def test_secure_snapshot_repository_targeted_load_of_the_same_row_already_refused_it(
    secure_objects: SecureObjectRepository,
) -> None:
    foreign = _probe_snapshot("snapshot-b")
    _save_probe_under_key(secure_objects, foreign, object_key_snapshot_id="snapshot-a")

    with pytest.raises(LiveApplicationInputError, match="does not match requested snapshot"):
        _probe_secure_repository(secure_objects).load("snapshot-a")


def test_secure_snapshot_repository_resolve_cannot_read_past_the_refusal(
    secure_objects: SecureObjectRepository,
) -> None:
    foreign = _probe_snapshot("snapshot-b")
    _save_probe_under_key(secure_objects, foreign, object_key_snapshot_id="snapshot-a")
    repo = _probe_secure_repository(secure_objects)

    with pytest.raises(LiveApplicationInputError) as exc_info:
        repo.resolve("snapshot-b")

    assert exc_info.value.translated_message == "application.live.snapshot_base.errors.snapshot_key_mismatch"


def test_snapshot_repository_protocol_anti_tautology() -> None:
    """Non-conforming object is not accepted; proves isinstance gate is real."""

    class NotARepo:
        """Intentionally missing all SnapshotRepository members."""

    assert not isinstance(NotARepo(), SnapshotRepository)


def test_every_lifecycle_state_has_a_filter_member_and_all_means_no_filter() -> None:
    """The filter axis must stay total over the lifecycle it filters.

    ``SnapshotStateFilter`` deliberately does NOT reuse ``SnapshotLifecycleState``:
    ``all`` is not a state a snapshot can be *in*, and admitting it to the lifecycle
    would give every exhaustive match a branch that cannot occur and let a stored
    record claim a state meaning "no filter".

    The cost of that separation is that a new lifecycle state could be added without
    a filter for it, silently making those snapshots unreachable from the CLI. This
    asserts the correspondence rather than a member count, so adding a lifecycle
    state reds this gate instead of quietly narrowing the operator's reach.
    """
    filterable = {member.value for member in SnapshotStateFilter} - {SnapshotStateFilter.ALL.value}
    assert filterable == {member.value for member in SnapshotLifecycleState}

    for member in SnapshotStateFilter:
        resolved = member.as_lifecycle_state()
        if member is SnapshotStateFilter.ALL:
            assert resolved is None
        else:
            assert resolved is SnapshotLifecycleState(member.value)
