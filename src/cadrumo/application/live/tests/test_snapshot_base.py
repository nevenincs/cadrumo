"""Real-behavior tests for the shared snapshot lifecycle base."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, override

import pytest
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ....core.errors.hierarchy import CadrumoError
from ....core.hashing import content_hash_hex
from ....core.identity.bucket import BucketId
from ..borrador_100 import BorradorSnapshotNotFoundError
from ..errors import LiveApplicationInputError
from ..snapshot_base import (
    SnapshotLifecycleState,
    SnapshotNotFoundError,
    SnapshotRepository,
    SnapshotService,
    SnapshotStateFilter,
    enforce_snapshot_state_invariants,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


_BUCKET_ID = "52525252-5252-4252-8252-525252525252"
_OTHER_BUCKET_ID = "53535353-5353-4353-8353-535353535353"


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


# ---- Test repository ------------------------------------------------------


class ProbeRepository:
    """In-memory inward fake satisfying ``SnapshotRepository[ProbeSnapshot]``."""

    def __init__(self, *, bucket_id: str) -> None:
        self._bucket_id = bucket_id.strip()
        if not self._bucket_id:
            raise LiveApplicationInputError("bucket_id must not be blank")
        self._snapshots: dict[str, ProbeSnapshot] = {}

    @property
    def bucket_id(self) -> str:
        return self._bucket_id

    def exists(self, snapshot_id: str) -> bool:
        return snapshot_id in self._snapshots

    def load(self, snapshot_id: str) -> ProbeSnapshot:
        try:
            return self._snapshots[snapshot_id]
        except KeyError as exc:
            raise LiveApplicationInputError(f"probe snapshot {snapshot_id!r} not found") from exc

    def list_snapshots(self) -> tuple[ProbeSnapshot, ...]:
        return tuple(sorted(self._snapshots.values(), key=lambda s: (s.captured_at, s.snapshot_id)))

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
        self._snapshots[snapshot.snapshot_id] = snapshot


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


def test_service_capture_persists_active_snapshot() -> None:
    repository = ProbeRepository(bucket_id=_BUCKET_ID)
    service = ProbeService(bucket_id=_BUCKET_ID, repository=repository)

    snapshot = service.capture(axis_label="renta-2025", captured_at=_CAPTURED_AT, payload_text="alpha")

    assert snapshot.state is SnapshotLifecycleState.ACTIVE
    assert snapshot.superseded_by_snapshot_id is None
    assert repository.load(snapshot.snapshot_id) == snapshot


def test_service_capture_deduplicates_by_content_id() -> None:
    repository = ProbeRepository(bucket_id=_BUCKET_ID)
    service = ProbeService(bucket_id=_BUCKET_ID, repository=repository)

    first = service.capture(axis_label="renta-2025", captured_at=_CAPTURED_AT, payload_text="alpha")
    second = service.capture(axis_label="renta-2025", captured_at=_CAPTURED_AT, payload_text="alpha")

    assert first == second
    assert len(repository.list_snapshots()) == 1


def test_service_capture_supersedes_prior_active_on_same_axis() -> None:
    repository = ProbeRepository(bucket_id=_BUCKET_ID)
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


def test_service_capture_demotes_late_arrival() -> None:
    repository = ProbeRepository(bucket_id=_BUCKET_ID)
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


def test_service_capture_does_not_supersede_across_axis() -> None:
    repository = ProbeRepository(bucket_id=_BUCKET_ID)
    service = ProbeService(bucket_id=_BUCKET_ID, repository=repository)

    first = service.capture(axis_label="renta-2025", captured_at=_CAPTURED_AT, payload_text="alpha")
    second = service.capture(
        axis_label="renta-2026",
        captured_at=_CAPTURED_AT + timedelta(hours=1),
        payload_text="beta",
    )

    assert repository.load(first.snapshot_id).state is SnapshotLifecycleState.ACTIVE
    assert repository.load(second.snapshot_id).state is SnapshotLifecycleState.ACTIVE


def test_service_resolve_snapshot_supports_prefix() -> None:
    repository = ProbeRepository(bucket_id=_BUCKET_ID)
    service = ProbeService(bucket_id=_BUCKET_ID, repository=repository)

    captured = service.capture(axis_label="renta-2025", captured_at=_CAPTURED_AT, payload_text="alpha")
    resolved = service.resolve_snapshot(captured.snapshot_id[:12])
    assert resolved == captured


def test_service_constructor_rejects_bucket_mismatch() -> None:
    repository = ProbeRepository(bucket_id=_BUCKET_ID)
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
    assert issubclass(SnapshotNotFoundError, CadrumoError)


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
