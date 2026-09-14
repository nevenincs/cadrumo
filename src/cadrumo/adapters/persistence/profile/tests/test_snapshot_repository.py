"""Persistence-adapter coverage for the generic secure snapshot repository."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict, Field, model_validator

from cadrumo.adapters.persistence.profile.snapshots import SecureSnapshotRepository
from cadrumo.adapters.persistence.storage.envelope.contract import Envelope
from cadrumo.adapters.persistence.storage.secure_object_namespaces import (
    LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE,
    TEST_SNAPSHOT_BASE_PROBE_NAMESPACE,
)
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.live.borrador_100 import (
    Borrador100Snapshot,
    Borrador100SnapshotRepository,
    BorradorSnapshotNotFoundError,
    borrador_100_snapshot_object_key,
)
from cadrumo.application.live.errors import LiveApplicationInputError
from cadrumo.application.live.snapshot_base import (
    SnapshotLifecycleState,
    SnapshotRepository,
    enforce_snapshot_state_invariants,
)
from cadrumo.core.identity.bucket import BucketId

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_PROBE_VERSION = 1
_BUCKET_ID = "52525252-5252-4252-8252-525252525252"
_OTHER_BUCKET_ID = "53535353-5353-4353-8353-535353535353"
_PROTO_BUCKET_ID = "54545454-5454-4454-8454-545454545454"
_CAPTURED_AT = datetime(2026, 4, 3, 10, 0, tzinfo=UTC)


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    """Bind this adapter test to an isolated encrypted profile store."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile.repository


class ProbeSnapshot(BaseModel):
    """Minimal payload used to exercise the generic persistence adapter."""

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


def _probe_object_key(bucket_id: str, snapshot_id: str) -> str:
    return f"snapshot-base-probe:{bucket_id}:{snapshot_id}"


def _probe_repository(secure_objects: SecureObjectRepository) -> SecureSnapshotRepository[ProbeSnapshot]:
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


def _borrador_repository(secure_objects: SecureObjectRepository) -> SecureSnapshotRepository[Borrador100Snapshot]:
    return SecureSnapshotRepository(
        bucket_id=_PROTO_BUCKET_ID,
        payload_model=Borrador100Snapshot,
        namespace_definition=LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE,
        object_key=borrador_100_snapshot_object_key,
        not_found_factory=lambda sid: BorradorSnapshotNotFoundError(
            translated_message="application.live.borrador.errors.snapshot_not_found",
            context={"snapshot_id": sid},
        ),
        ambiguous_prefix_factory=lambda sid, ids: BorradorSnapshotNotFoundError(
            translated_message="application.live.borrador.errors.snapshot_prefix_ambiguous",
            context={"snapshot_id": sid, "match_count": len(ids)},
        ),
        domain_label="borrador",
        input_error_cls=LiveApplicationInputError,
        objects=secure_objects,
    )


def _save_probe_under_key(
    secure_objects: SecureObjectRepository,
    snapshot: ProbeSnapshot,
    *,
    object_key_snapshot_id: str,
) -> None:
    """Persist a valid payload under a deliberately selected row key."""
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
        schema_version=_PROBE_VERSION,
        written_at=envelope.written_at,
        payload=envelope.model_dump_json().encode("utf-8"),
    )


def _probe_snapshot(snapshot_id: str, *, bucket_id: str = _BUCKET_ID) -> ProbeSnapshot:
    return ProbeSnapshot(
        snapshot_id=snapshot_id,
        bucket_id=bucket_id,
        axis_label="renta-2025",
        captured_at=_CAPTURED_AT,
        payload_text="body",
        state=SnapshotLifecycleState.ACTIVE,
    )


def test_borrador100_snapshot_repository_conforms_to_protocol(
    secure_objects: SecureObjectRepository,
) -> None:
    """The real secure adapter satisfies the application Borrador port structurally."""
    repo = _borrador_repository(secure_objects)
    assert isinstance(repo, Borrador100SnapshotRepository)
    assert Borrador100SnapshotRepository not in type(repo).__mro__


def test_secure_snapshot_repository_conforms_to_protocol(
    secure_objects: SecureObjectRepository,
) -> None:
    """The generic secure adapter satisfies the shared application port structurally."""
    assert isinstance(_probe_repository(secure_objects), SnapshotRepository)


def test_secure_snapshot_repository_list_rejects_payload_bucket_mismatch(
    secure_objects: SecureObjectRepository,
) -> None:
    snapshot = _probe_snapshot("misrouted-snapshot", bucket_id=_OTHER_BUCKET_ID)
    _save_probe_under_key(secure_objects, snapshot, object_key_snapshot_id=snapshot.snapshot_id)

    with pytest.raises(LiveApplicationInputError) as exc_info:
        _probe_repository(secure_objects).list_snapshots()

    assert exc_info.value.translated_message == "application.live.snapshot_base.errors.snapshot_bucket_mismatch"
    assert exc_info.value.context == {
        "domain_label": "probe",
        "snapshot_bucket": _OTHER_BUCKET_ID,
        "repository_bucket": _BUCKET_ID,
    }


def test_secure_snapshot_repository_list_returns_a_snapshot_under_its_own_key(
    secure_objects: SecureObjectRepository,
) -> None:
    snapshot = _probe_snapshot("snapshot-a")
    _save_probe_under_key(secure_objects, snapshot, object_key_snapshot_id="snapshot-a")

    assert _probe_repository(secure_objects).list_snapshots() == (snapshot,)


def test_secure_snapshot_repository_list_rejects_a_snapshot_under_a_foreign_key(
    secure_objects: SecureObjectRepository,
) -> None:
    """A valid payload stored under another snapshot key must not enumerate."""
    foreign = _probe_snapshot("snapshot-b")
    _save_probe_under_key(secure_objects, foreign, object_key_snapshot_id="snapshot-a")

    with pytest.raises(LiveApplicationInputError) as exc_info:
        _probe_repository(secure_objects).list_snapshots()

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
        _probe_repository(secure_objects).load("snapshot-a")


def test_secure_snapshot_repository_resolve_cannot_read_past_the_refusal(
    secure_objects: SecureObjectRepository,
) -> None:
    foreign = _probe_snapshot("snapshot-b")
    _save_probe_under_key(secure_objects, foreign, object_key_snapshot_id="snapshot-a")

    with pytest.raises(LiveApplicationInputError) as exc_info:
        _probe_repository(secure_objects).resolve("snapshot-b")

    assert exc_info.value.translated_message == "application.live.snapshot_base.errors.snapshot_key_mismatch"
