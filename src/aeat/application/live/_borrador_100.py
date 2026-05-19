"""Application-live persistence for captured Modelo 100 borrador snapshots.

Borrador100 is the proof-of-concept consumer of the shared
``_snapshot_base`` lifecycle abstraction. The public exception class names
(``LiveApplicationInputError``-derived), ``Borrador100SnapshotService``
class identity, storage namespace, object-key layout, and method
signatures are preserved exactly; only the inline state-machine,
supersession, and content-id helpers have been routed through the
shared base.

``Borrador100SnapshotState`` remains exported under its original name and
is now an alias of :class:`SnapshotLifecycleState`, since the enum value
names already match the canonical lifecycle vocabulary.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...adapters.persistence.storage import Envelope, SensitivityClass
from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError
from ...adapters.persistence.storage.sql import SecureObjectRecord, SecureObjectRepository
from ._errors import LiveApplicationInputError
from ._snapshot_base import (
    SnapshotLifecycleState,
    SnapshotService,
    derive_snapshot_id_from_json,
    enforce_snapshot_state_invariants,
)

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")
BORRADOR_100_SNAPSHOT_NAMESPACE = "aeat.application.live.borrador_100_snapshot"
_BORRADOR_100_SNAPSHOT_VERSION = 1
type _BorradorValue = Decimal | str


# Borrador100SnapshotState retained as a named alias so existing imports keep
# working unchanged. Phase 1 deviation from the proposal: the proposal
# suggested a subclass enum; the existing Borrador100 enum already uses the
# canonical value names ("active"/"superseded"/"discarded") so we alias the
# shared enum directly rather than introducing a duplicate StrEnum.
Borrador100SnapshotState = SnapshotLifecycleState


class Borrador100Snapshot(BaseModel):
    """Captured Modelo 100 borrador values available to application consumers."""

    model_config = _STRICT_FROZEN

    snapshot_id: str = Field(min_length=1, max_length=128)
    bucket_id: str = Field(min_length=1, max_length=128)
    modelo: str = Field(pattern=r"^100$")
    filing_year: int = Field(ge=1900, le=9999)
    period: str = Field(min_length=1, max_length=16)
    captured_at: datetime
    source_url: str = Field(min_length=1, max_length=2048)
    state: SnapshotLifecycleState
    binding_values: Mapping[str, _BorradorValue] = Field(default_factory=dict)
    superseded_by_snapshot_id: str | None = Field(default=None, min_length=1, max_length=128)
    discarded_at: datetime | None = None
    discarded_by: str = Field(default="", max_length=128)
    discard_reason: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def _enforce_state_payload(self) -> Borrador100Snapshot:
        enforce_snapshot_state_invariants(
            state=self.state,
            has_supersession_pointer=self.superseded_by_snapshot_id is not None,
            discarded_at=self.discarded_at,
            discarded_by=self.discarded_by,
            discard_reason=self.discard_reason,
        )
        blank_keys = sorted(key for key in self.binding_values if not key.strip())
        if blank_keys:
            raise LiveApplicationInputError("borrador binding value keys must not be blank")
        return self


def borrador_100_snapshot_object_key(bucket_id: str, snapshot_id: str) -> str:
    """Return the secure-object key for one bucket's Modelo 100 borrador snapshot."""

    trimmed_bucket = bucket_id.strip()
    trimmed_snapshot = snapshot_id.strip()
    if not trimmed_bucket:
        raise LiveApplicationInputError("bucket_id must not be blank")
    if not trimmed_snapshot:
        raise LiveApplicationInputError("snapshot_id must not be blank")
    return f"modelo-100-borrador-snapshot:{trimmed_bucket}:{trimmed_snapshot}"


def derive_borrador_100_snapshot_id(
    *,
    filing_year: int,
    period: str,
    captured_at: datetime,
    source_url: str,
    binding_values: Mapping[str, _BorradorValue],
) -> str:
    """Return the content-addressed id for one Modelo 100 borrador capture.

    The canonical-JSON shape is preserved exactly so existing on-disk
    snapshot ids remain valid: routing through
    ``derive_snapshot_id_from_json`` does not change the hashed bytes.
    """

    return derive_snapshot_id_from_json(
        {
            "modelo": "100",
            "filing_year": filing_year,
            "period": period.strip(),
            "captured_at": captured_at.isoformat(),
            "source_url": source_url,
            "binding_values": {
                key: format(value, "f") if isinstance(value, Decimal) else value
                for key, value in sorted(binding_values.items())
            },
        }
    )


def _snapshot_from_record(record: SecureObjectRecord, requested_snapshot_id: str | None = None) -> Borrador100Snapshot:
    envelope = Envelope[Borrador100Snapshot].model_validate_json(record.payload.decode("utf-8"))
    if envelope.classification is not SensitivityClass.FINANCIAL:
        snapshot_label = requested_snapshot_id or envelope.payload.snapshot_id
        raise ClassificationError(
            f"borrador snapshot {snapshot_label!r} has classification {envelope.classification}; "
            f"consumer expected {SensitivityClass.FINANCIAL}",
        )
    if envelope.schema_version > _BORRADOR_100_SNAPSHOT_VERSION:
        snapshot_label = requested_snapshot_id or envelope.payload.snapshot_id
        raise EnvelopeVersionError(
            f"borrador snapshot {snapshot_label!r} is at version {envelope.schema_version}; "
            f"consumer supports up to {_BORRADOR_100_SNAPSHOT_VERSION}",
        )
    return envelope.payload


class Borrador100SnapshotRepository:
    """Secure-DB repository for captured Modelo 100 borrador snapshots."""

    def __init__(self, *, bucket_id: str, objects: SecureObjectRepository | None = None) -> None:
        self._bucket_id = bucket_id.strip()
        if not self._bucket_id:
            raise LiveApplicationInputError("bucket_id must not be blank")
        self._objects = objects or SecureObjectRepository()

    @property
    def bucket_id(self) -> str:
        return self._bucket_id

    def exists(self, snapshot_id: str) -> bool:
        return self._objects.exists(
            BORRADOR_100_SNAPSHOT_NAMESPACE,
            borrador_100_snapshot_object_key(self._bucket_id, snapshot_id),
        )

    def load(self, snapshot_id: str) -> Borrador100Snapshot:
        record = self._objects.load(
            BORRADOR_100_SNAPSHOT_NAMESPACE,
            borrador_100_snapshot_object_key(self._bucket_id, snapshot_id),
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_BORRADOR_100_SNAPSHOT_VERSION,
        )
        if record is None:
            raise LiveApplicationInputError(
                f"borrador snapshot {snapshot_id!r} not found in bucket {self._bucket_id!r}",
                suggestion="aeat app live borrador 100 list",
            )
        snapshot = _snapshot_from_record(record, requested_snapshot_id=snapshot_id)
        if snapshot.bucket_id != self._bucket_id:
            raise LiveApplicationInputError(
                f"borrador snapshot payload bucket_id={snapshot.bucket_id!r} "
                f"does not match repository bucket {self._bucket_id!r}"
            )
        if snapshot.snapshot_id != snapshot_id:
            raise LiveApplicationInputError(
                f"borrador snapshot payload id={snapshot.snapshot_id!r} "
                f"does not match requested snapshot {snapshot_id!r}"
            )
        return snapshot

    def list_snapshots(self) -> tuple[Borrador100Snapshot, ...]:
        snapshots = [
            snapshot
            for record in self._objects.list_records(
                BORRADOR_100_SNAPSHOT_NAMESPACE,
                expected_class=SensitivityClass.FINANCIAL,
                max_supported_version=_BORRADOR_100_SNAPSHOT_VERSION,
            )
            for snapshot in (_snapshot_from_record(record),)
            if snapshot.bucket_id == self._bucket_id
        ]
        return tuple(sorted(snapshots, key=lambda item: (item.captured_at, item.snapshot_id)))

    def resolve(self, snapshot_id: str) -> Borrador100Snapshot:
        trimmed_snapshot_id = snapshot_id.strip()
        if not trimmed_snapshot_id:
            raise LiveApplicationInputError("snapshot_id must not be blank")
        matches = [
            snapshot
            for snapshot in self.list_snapshots()
            if snapshot.snapshot_id == trimmed_snapshot_id or snapshot.snapshot_id.startswith(trimmed_snapshot_id)
        ]
        if not matches:
            raise LiveApplicationInputError(
                f"borrador snapshot {snapshot_id!r} not found in bucket {self._bucket_id!r}",
                suggestion="aeat app live borrador 100 list",
            )
        if len(matches) > 1:
            raise LiveApplicationInputError(
                f"borrador snapshot prefix {snapshot_id!r} is ambiguous",
                suggestion="provide a longer snapshot id",
            )
        return matches[0]

    def save(self, snapshot: Borrador100Snapshot) -> None:
        if snapshot.bucket_id != self._bucket_id:
            raise LiveApplicationInputError(
                f"borrador snapshot bucket_id={snapshot.bucket_id!r} "
                f"does not match repository bucket {self._bucket_id!r}"
            )
        envelope = Envelope[Borrador100Snapshot](
            schema_version=_BORRADOR_100_SNAPSHOT_VERSION,
            written_at=datetime.now(UTC),
            classification=SensitivityClass.FINANCIAL,
            payload=snapshot,
        )
        self._objects.save(
            namespace=BORRADOR_100_SNAPSHOT_NAMESPACE,
            object_key=borrador_100_snapshot_object_key(self._bucket_id, snapshot.snapshot_id),
            classification=SensitivityClass.FINANCIAL,
            schema_version=_BORRADOR_100_SNAPSHOT_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )


class Borrador100SnapshotService(SnapshotService[Borrador100Snapshot]):
    """Canonical backend service for bucket-scoped Modelo 100 borrador snapshots."""

    def __init__(
        self,
        *,
        bucket_id: str,
        repository: Borrador100SnapshotRepository | None = None,
    ) -> None:
        resolved_repository = repository or Borrador100SnapshotRepository(bucket_id=bucket_id)
        super().__init__(bucket_id=bucket_id, repository=resolved_repository)

    # ---- public API (signatures unchanged for external callers) ----------

    def capture(
        self,
        *,
        filing_year: int,
        period: str,
        captured_at: datetime,
        source_url: str,
        binding_values: Mapping[str, _BorradorValue],
    ) -> Borrador100Snapshot:
        return self._capture_with_lifecycle(
            filing_year=filing_year,
            period=period,
            captured_at=captured_at,
            source_url=source_url,
            binding_values=binding_values,
        )

    def list_snapshots(  # type: ignore[override]
        self,
        *,
        filing_year: int | None = None,
        state: SnapshotLifecycleState | None = SnapshotLifecycleState.ACTIVE,
    ) -> tuple[Borrador100Snapshot, ...]:
        snapshots: tuple[Borrador100Snapshot, ...] = super().list_snapshots()
        if filing_year is not None:
            snapshots = tuple(snapshot for snapshot in snapshots if snapshot.filing_year == filing_year)
        if state is not None:
            snapshots = tuple(snapshot for snapshot in snapshots if snapshot.state is state)
        return snapshots

    def show(self, snapshot_id: str) -> Borrador100Snapshot:
        return self.resolve_snapshot(snapshot_id)

    def latest_for_year(self, *, filing_year: int, period: str | None = None) -> Borrador100Snapshot | None:
        snapshots = [
            snapshot
            for snapshot in self.list_snapshots(filing_year=filing_year)
            if period is None or snapshot.period == period.strip()
        ]
        if not snapshots:
            return None
        return max(snapshots, key=lambda snapshot: snapshot.captured_at)

    # ---- SnapshotService[Borrador100Snapshot] hooks ----------------------

    def _derive_snapshot_id(self, **kwargs: Any) -> str:
        return derive_borrador_100_snapshot_id(
            filing_year=kwargs["filing_year"],
            period=kwargs["period"],
            captured_at=kwargs["captured_at"],
            source_url=kwargs["source_url"],
            binding_values=kwargs["binding_values"],
        )

    def _build_active_payload(self, *, snapshot_id: str, **kwargs: Any) -> Borrador100Snapshot:
        return Borrador100Snapshot(
            snapshot_id=snapshot_id,
            bucket_id=self._repository.bucket_id,
            modelo="100",
            filing_year=kwargs["filing_year"],
            period=kwargs["period"].strip(),
            captured_at=kwargs["captured_at"],
            source_url=kwargs["source_url"],
            state=SnapshotLifecycleState.ACTIVE,
            binding_values=dict(kwargs["binding_values"]),
        )

    def _payload_axis_key(self, payload: Borrador100Snapshot) -> tuple[Any, ...]:
        return (payload.modelo, payload.filing_year, payload.period)

    def _payload_captured_at(self, payload: Borrador100Snapshot) -> datetime:
        return payload.captured_at

    def _payload_snapshot_id(self, payload: Borrador100Snapshot) -> str:
        return payload.snapshot_id

    def _payload_state(self, payload: Borrador100Snapshot) -> SnapshotLifecycleState:
        return payload.state

    def _demote_to_superseded(
        self, payload: Borrador100Snapshot, *, superseded_by: str
    ) -> Borrador100Snapshot:
        return payload.model_copy(
            update={
                "state": SnapshotLifecycleState.SUPERSEDED,
                "superseded_by_snapshot_id": superseded_by,
            }
        )


__all__ = [
    "BORRADOR_100_SNAPSHOT_NAMESPACE",
    "Borrador100Snapshot",
    "Borrador100SnapshotRepository",
    "Borrador100SnapshotService",
    "Borrador100SnapshotState",
    "borrador_100_snapshot_object_key",
    "derive_borrador_100_snapshot_id",
]
