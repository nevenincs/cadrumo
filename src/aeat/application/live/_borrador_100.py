"""Application-live persistence for captured Modelo 100 borrador snapshots."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...adapters.persistence.storage import Envelope, SensitivityClass
from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError
from ...adapters.persistence.storage.sql import SecureObjectRecord, SecureObjectRepository
from ._errors import LiveApplicationInputError

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")
BORRADOR_100_SNAPSHOT_NAMESPACE = "aeat.application.live.borrador_100_snapshot"
_BORRADOR_100_SNAPSHOT_VERSION = 1
type _BorradorValue = Decimal | str


class Borrador100SnapshotState(StrEnum):
    """Lifecycle state relevant to calculation-time consumption."""

    ACTIVE = "active"
    SUPERSEDED = "superseded"
    DISCARDED = "discarded"


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
    state: Borrador100SnapshotState
    binding_values: Mapping[str, _BorradorValue] = Field(default_factory=dict)
    superseded_by_snapshot_id: str | None = Field(default=None, min_length=1, max_length=128)
    discarded_at: datetime | None = None
    discarded_by: str = Field(default="", max_length=128)
    discard_reason: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def _enforce_state_payload(self) -> Borrador100Snapshot:
        if self.state is Borrador100SnapshotState.ACTIVE and self.superseded_by_snapshot_id is not None:
            raise LiveApplicationInputError("active borrador snapshots cannot carry supersession pointers")
        if self.state is Borrador100SnapshotState.SUPERSEDED and self.superseded_by_snapshot_id is None:
            raise LiveApplicationInputError("superseded borrador snapshots must carry superseded_by_snapshot_id")
        if self.state is not Borrador100SnapshotState.DISCARDED:
            if self.discarded_at is not None or self.discarded_by or self.discard_reason:
                raise LiveApplicationInputError("only discarded borrador snapshots can carry discard metadata")
        elif self.discarded_at is None or not self.discarded_by.strip():
            raise LiveApplicationInputError("discarded borrador snapshots require discarded_at and discarded_by")
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
    """Return the content-addressed id for one Modelo 100 borrador capture."""

    canonical = json.dumps(
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
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


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


class Borrador100SnapshotService:
    """Canonical backend service for bucket-scoped Modelo 100 borrador snapshots."""

    def __init__(
        self,
        *,
        bucket_id: str,
        repository: Borrador100SnapshotRepository | None = None,
    ) -> None:
        self._repository = repository or Borrador100SnapshotRepository(bucket_id=bucket_id)
        if self._repository.bucket_id != bucket_id.strip():
            raise LiveApplicationInputError(
                f"borrador service bucket_id={bucket_id!r} does not match repository bucket "
                f"{self._repository.bucket_id!r}"
            )

    def capture(
        self,
        *,
        filing_year: int,
        period: str,
        captured_at: datetime,
        source_url: str,
        binding_values: Mapping[str, _BorradorValue],
    ) -> Borrador100Snapshot:
        snapshot_id = derive_borrador_100_snapshot_id(
            filing_year=filing_year,
            period=period,
            captured_at=captured_at,
            source_url=source_url,
            binding_values=binding_values,
        )
        if self._repository.exists(snapshot_id):
            return self._repository.load(snapshot_id)
        snapshot = Borrador100Snapshot(
            snapshot_id=snapshot_id,
            bucket_id=self._repository.bucket_id,
            modelo="100",
            filing_year=filing_year,
            period=period.strip(),
            captured_at=captured_at,
            source_url=source_url,
            state=Borrador100SnapshotState.ACTIVE,
            binding_values=dict(binding_values),
        )
        active_snapshot = self._latest_active_for_axis(snapshot)
        if active_snapshot is not None and active_snapshot.captured_at > snapshot.captured_at:
            snapshot = snapshot.model_copy(
                update={
                    "state": Borrador100SnapshotState.SUPERSEDED,
                    "superseded_by_snapshot_id": active_snapshot.snapshot_id,
                }
            )
            self._repository.save(snapshot)
            return snapshot
        self._supersede_current_for_axis(snapshot)
        self._repository.save(snapshot)
        return snapshot

    def list_snapshots(
        self,
        *,
        filing_year: int | None = None,
        state: Borrador100SnapshotState | None = Borrador100SnapshotState.ACTIVE,
    ) -> tuple[Borrador100Snapshot, ...]:
        snapshots = self._repository.list_snapshots()
        if filing_year is not None:
            snapshots = tuple(snapshot for snapshot in snapshots if snapshot.filing_year == filing_year)
        if state is not None:
            snapshots = tuple(snapshot for snapshot in snapshots if snapshot.state is state)
        return snapshots

    def show(self, snapshot_id: str) -> Borrador100Snapshot:
        return self._repository.resolve(snapshot_id)

    def latest_for_year(self, *, filing_year: int, period: str | None = None) -> Borrador100Snapshot | None:
        snapshots = [
            snapshot
            for snapshot in self.list_snapshots(filing_year=filing_year)
            if period is None or snapshot.period == period.strip()
        ]
        if not snapshots:
            return None
        return max(snapshots, key=lambda snapshot: snapshot.captured_at)

    def _supersede_current_for_axis(self, replacement: Borrador100Snapshot) -> None:
        for snapshot in self._repository.list_snapshots():
            if (
                snapshot.snapshot_id != replacement.snapshot_id
                and snapshot.modelo == replacement.modelo
                and snapshot.filing_year == replacement.filing_year
                and snapshot.period == replacement.period
                and snapshot.state is Borrador100SnapshotState.ACTIVE
            ):
                self._repository.save(
                    snapshot.model_copy(
                        update={
                            "state": Borrador100SnapshotState.SUPERSEDED,
                            "superseded_by_snapshot_id": replacement.snapshot_id,
                        }
                    )
                )

    def _latest_active_for_axis(self, snapshot: Borrador100Snapshot) -> Borrador100Snapshot | None:
        active = [
            candidate
            for candidate in self._repository.list_snapshots()
            if (
                candidate.snapshot_id != snapshot.snapshot_id
                and candidate.modelo == snapshot.modelo
                and candidate.filing_year == snapshot.filing_year
                and candidate.period == snapshot.period
                and candidate.state is Borrador100SnapshotState.ACTIVE
            )
        ]
        if not active:
            return None
        return max(active, key=lambda candidate: (candidate.captured_at, candidate.snapshot_id))


__all__ = [
    "BORRADOR_100_SNAPSHOT_NAMESPACE",
    "Borrador100Snapshot",
    "Borrador100SnapshotRepository",
    "Borrador100SnapshotService",
    "Borrador100SnapshotState",
    "borrador_100_snapshot_object_key",
    "derive_borrador_100_snapshot_id",
]
