"""Application-live persistence for captured Modelo 036 census snapshots.

`CensusSnapshot` holds the AEAT-side census facts the operator's
profile must mirror per the 2026-05-16 amendment to the
modelo-036-037-foundation ADR. AEAT is the binding legal source of
truth; the local profile is a cache that must be kept honest.

The snapshot pattern mirrors :mod:`aeat.application.live._borrador_100`:
content-addressed snapshot ids, encrypted SQLite persistence under a
namespaced secure-object key, and a closed ACTIVE / SUPERSEDED /
DISCARDED state machine. Re-fetch auto-supersedes the prior ACTIVE
snapshot for the same profile.

The CLI-facing `CensusSyncService` is the only caller; the
sede G313 adapter populates `census_facts` from the live
Mis Datos Censales endpoint.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
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

CENSUS_SNAPSHOT_NAMESPACE = "aeat.application.live.census_snapshot"
_CENSUS_SNAPSHOT_VERSION = 1

# census_facts values are always strings: enum values, ISO date strings,
# NIF strings, and decimal-as-string for the vivienda_office m2 inputs.
# A union Decimal | str silently coerces numeric-looking strings (e.g.
# "15") into Decimal on JSON round-trip, breaking equality and the
# typed-distinction operators expect (the elected_withholding_pct enum
# value is "15" not Decimal("15")). The sede HTML extractor produces
# strings; the engine that consumes the snapshot parses the m2 strings
# back to Decimal at calculation time.
type _CensusFactValue = str


# CensusSnapshotState retained as a named alias so existing imports keep
# working unchanged. The Census enum values already match the canonical
# lifecycle vocabulary ("active"/"superseded"/"discarded") so we alias the
# shared enum directly rather than maintain a duplicate StrEnum.
CensusSnapshotState = SnapshotLifecycleState


class CensusSnapshot(BaseModel):
    """Captured 036 census facts available to application consumers.

    `census_facts` is a flat mapping keyed by the dotted schema path
    (e.g. ``census.activity_start_date``, ``vivienda_office.office_m2``,
    ``contact.fiscal_address_cadastral_reference``). Values are either
    decimal strings (for the raw m2 inputs) or short literals
    (enum values, ISO dates, NIF strings).

    Attributes:
        snapshot_id: Content-addressed SHA-256 hex over
            ``(profile_id, captured_at, source_url, census_facts)``.
        bucket_id: Active profile bucket id at capture time. Snapshots
            are bucket-scoped so cross-profile leakage is impossible.
        profile_id: Operator profile identifier the snapshot belongs
            to. Carried separately from bucket_id so multi-profile
            buckets remain addressable.
        captured_at: UTC timestamp at which the sede read completed.
        source_url: The G313 sede endpoint the snapshot was extracted
            from. Audited so operators can trace each capture back to
            its AEAT origin.
        state: Lifecycle state from :class:`CensusSnapshotState`.
        census_facts: Flat mapping from dotted schema path to the
            AEAT-side value. The CensusSyncService.compare verb
            walks this mapping against the local profile.
        superseded_by_snapshot_id: Pointer to the snapshot that
            replaced this one. Required when ``state is SUPERSEDED``;
            absent otherwise.
        discarded_at, discarded_by, discard_reason: Audit metadata
            captured when the operator explicitly retired the snapshot.
    """

    model_config = _STRICT_FROZEN

    snapshot_id: str = Field(min_length=1, max_length=128)
    bucket_id: str = Field(min_length=1, max_length=128)
    profile_id: str = Field(min_length=1, max_length=128)
    captured_at: datetime
    source_url: str = Field(min_length=1, max_length=2048)
    state: SnapshotLifecycleState
    census_facts: Mapping[str, _CensusFactValue] = Field(default_factory=dict)
    superseded_by_snapshot_id: str | None = Field(default=None, min_length=1, max_length=128)
    discarded_at: datetime | None = None
    discarded_by: str = Field(default="", max_length=128)
    discard_reason: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def _enforce_state_payload(self) -> CensusSnapshot:
        enforce_snapshot_state_invariants(
            state=self.state,
            has_supersession_pointer=self.superseded_by_snapshot_id is not None,
            discarded_at=self.discarded_at,
            discarded_by=self.discarded_by,
            discard_reason=self.discard_reason,
        )
        blank_keys = sorted(key for key in self.census_facts if not key.strip())
        if blank_keys:
            raise LiveApplicationInputError("census fact keys must not be blank")
        return self


def census_snapshot_object_key(bucket_id: str, snapshot_id: str) -> str:
    """Return the secure-object key for one bucket's census snapshot."""

    trimmed_bucket = bucket_id.strip()
    trimmed_snapshot = snapshot_id.strip()
    if not trimmed_bucket:
        raise LiveApplicationInputError("bucket_id must not be blank")
    if not trimmed_snapshot:
        raise LiveApplicationInputError("snapshot_id must not be blank")
    return f"census-snapshot:{trimmed_bucket}:{trimmed_snapshot}"


def derive_census_snapshot_id(
    *,
    profile_id: str,
    captured_at: datetime,
    source_url: str,
    census_facts: Mapping[str, _CensusFactValue],
) -> str:
    """Return the content-addressed id for one census capture.

    Two structurally identical snapshots (same profile, same captured-
    at instant, same source, same fact values) produce the same id;
    re-saving is then a no-op via :meth:`CensusSnapshotService.refresh`.
    """

    return derive_snapshot_id_from_json(
        {
            "profile_id": profile_id.strip(),
            "captured_at": captured_at.isoformat(),
            "source_url": source_url,
            "census_facts": dict(sorted(census_facts.items())),
        }
    )


def _snapshot_from_record(
    record: SecureObjectRecord,
    requested_snapshot_id: str | None = None,
) -> CensusSnapshot:
    envelope = Envelope[CensusSnapshot].model_validate_json(record.payload.decode("utf-8"))
    if envelope.classification is not SensitivityClass.IDENTITY:
        snapshot_label = requested_snapshot_id or envelope.payload.snapshot_id
        raise ClassificationError(
            f"census snapshot {snapshot_label!r} has classification {envelope.classification}; "
            f"consumer expected {SensitivityClass.IDENTITY}",
        )
    if envelope.schema_version > _CENSUS_SNAPSHOT_VERSION:
        snapshot_label = requested_snapshot_id or envelope.payload.snapshot_id
        raise EnvelopeVersionError(
            f"census snapshot {snapshot_label!r} is at version {envelope.schema_version}; "
            f"consumer supports up to {_CENSUS_SNAPSHOT_VERSION}",
        )
    return envelope.payload


class CensusSnapshotRepository:
    """Secure-DB repository for captured 036 census snapshots."""

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
            CENSUS_SNAPSHOT_NAMESPACE,
            census_snapshot_object_key(self._bucket_id, snapshot_id),
        )

    def load(self, snapshot_id: str) -> CensusSnapshot:
        record = self._objects.load(
            CENSUS_SNAPSHOT_NAMESPACE,
            census_snapshot_object_key(self._bucket_id, snapshot_id),
            expected_class=SensitivityClass.IDENTITY,
            max_supported_version=_CENSUS_SNAPSHOT_VERSION,
        )
        if record is None:
            raise LiveApplicationInputError(
                f"census snapshot {snapshot_id!r} not found in bucket {self._bucket_id!r}",
                suggestion="aeat config profile census refresh",
            )
        snapshot = _snapshot_from_record(record, requested_snapshot_id=snapshot_id)
        if snapshot.bucket_id != self._bucket_id:
            raise LiveApplicationInputError(
                f"census snapshot payload bucket_id={snapshot.bucket_id!r} "
                f"does not match repository bucket {self._bucket_id!r}",
            )
        if snapshot.snapshot_id != snapshot_id:
            raise LiveApplicationInputError(
                f"census snapshot payload id={snapshot.snapshot_id!r} "
                f"does not match requested snapshot {snapshot_id!r}",
            )
        return snapshot

    def list_snapshots(self) -> tuple[CensusSnapshot, ...]:
        snapshots = [
            snapshot
            for record in self._objects.list_records(
                CENSUS_SNAPSHOT_NAMESPACE,
                expected_class=SensitivityClass.IDENTITY,
                max_supported_version=_CENSUS_SNAPSHOT_VERSION,
            )
            for snapshot in (_snapshot_from_record(record),)
            if snapshot.bucket_id == self._bucket_id
        ]
        return tuple(sorted(snapshots, key=lambda item: (item.captured_at, item.snapshot_id)))

    def resolve(self, snapshot_id: str) -> CensusSnapshot:
        trimmed_snapshot_id = snapshot_id.strip()
        if not trimmed_snapshot_id:
            raise LiveApplicationInputError("snapshot_id must not be blank")
        matches = [
            snapshot
            for snapshot in self.list_snapshots()
            if snapshot.snapshot_id == trimmed_snapshot_id
            or snapshot.snapshot_id.startswith(trimmed_snapshot_id)
        ]
        if not matches:
            raise LiveApplicationInputError(
                f"census snapshot {snapshot_id!r} not found in bucket {self._bucket_id!r}",
                suggestion="aeat config profile census refresh",
            )
        if len(matches) > 1:
            raise LiveApplicationInputError(
                f"census snapshot prefix {snapshot_id!r} is ambiguous",
                suggestion="provide a longer snapshot id",
            )
        return matches[0]

    def save(self, snapshot: CensusSnapshot) -> None:
        if snapshot.bucket_id != self._bucket_id:
            raise LiveApplicationInputError(
                f"census snapshot bucket_id={snapshot.bucket_id!r} "
                f"does not match repository bucket {self._bucket_id!r}",
            )
        envelope = Envelope[CensusSnapshot](
            schema_version=_CENSUS_SNAPSHOT_VERSION,
            written_at=datetime.now(UTC),
            classification=SensitivityClass.IDENTITY,
            payload=snapshot,
        )
        self._objects.save(
            namespace=CENSUS_SNAPSHOT_NAMESPACE,
            object_key=census_snapshot_object_key(self._bucket_id, snapshot.snapshot_id),
            classification=SensitivityClass.IDENTITY,
            schema_version=_CENSUS_SNAPSHOT_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )


class CensusSnapshotService(SnapshotService[CensusSnapshot]):
    """Canonical backend service for bucket-scoped 036 census snapshots.

    Mirrors :class:`Borrador100SnapshotService`. The CLI's
    `CensusSyncService.refresh_census` is the only caller of
    :meth:`capture`; `show_census` reads via :meth:`latest_active`
    and :meth:`resolve_snapshot`; `apply_census_to_profile` reads
    via :meth:`latest_active`.

    The caller is responsible for emitting the
    `CENSUS_REFRESHED` bucket event after a successful capture (the
    snapshot service itself is intentionally event-free so the same
    machinery can be exercised from test scaffolding without
    polluting the bucket-event-history catalogue).
    """

    def __init__(
        self,
        *,
        bucket_id: str,
        repository: CensusSnapshotRepository | None = None,
    ) -> None:
        resolved_repository = repository or CensusSnapshotRepository(bucket_id=bucket_id)
        super().__init__(bucket_id=bucket_id, repository=resolved_repository)

    # ---- public API (signatures unchanged for external callers) ----------

    def capture(
        self,
        *,
        profile_id: str,
        captured_at: datetime,
        source_url: str,
        census_facts: Mapping[str, _CensusFactValue],
    ) -> CensusSnapshot:
        """Persist a new census snapshot and auto-supersede prior ACTIVE.

        Re-capturing structurally identical facts (same profile / time /
        source / values) is a no-op: the existing snapshot is loaded
        and returned without supersession.
        """

        return self._capture_with_lifecycle(
            profile_id=profile_id,
            captured_at=captured_at,
            source_url=source_url,
            census_facts=census_facts,
        )

    def list_snapshots(  # type: ignore[override]
        self,
        *,
        profile_id: str | None = None,
        state: SnapshotLifecycleState | None = SnapshotLifecycleState.ACTIVE,
    ) -> tuple[CensusSnapshot, ...]:
        snapshots: tuple[CensusSnapshot, ...] = super().list_snapshots()
        if profile_id is not None:
            trimmed = profile_id.strip()
            snapshots = tuple(snapshot for snapshot in snapshots if snapshot.profile_id == trimmed)
        if state is not None:
            snapshots = tuple(snapshot for snapshot in snapshots if snapshot.state is state)
        return snapshots

    def latest_active(self, *, profile_id: str) -> CensusSnapshot | None:
        snapshots = self.list_snapshots(profile_id=profile_id)
        if not snapshots:
            return None
        return max(snapshots, key=lambda snapshot: snapshot.captured_at)

    def discard(
        self,
        *,
        snapshot_id: str,
        discarded_by: str,
        discard_reason: str = "",
    ) -> CensusSnapshot:
        """Mark a snapshot as DISCARDED. Local-only; never contacts AEAT.

        Used when the operator explicitly retires a snapshot captured
        from a sede outage or with malformed values. The discard does
        not delete the secure object; it transitions the state so
        downstream consumers ignore the snapshot.
        """

        trimmed_actor = discarded_by.strip()
        if not trimmed_actor:
            raise LiveApplicationInputError("discarded_by must not be blank")
        existing = self._repository.resolve(snapshot_id)
        if existing.state is SnapshotLifecycleState.DISCARDED:
            return existing
        updated = existing.model_copy(
            update={
                "state": SnapshotLifecycleState.DISCARDED,
                "discarded_at": datetime.now(UTC),
                "discarded_by": trimmed_actor,
                "discard_reason": discard_reason.strip(),
                "superseded_by_snapshot_id": None,
            },
        )
        self._repository.save(updated)
        return updated

    # ---- SnapshotService[CensusSnapshot] hooks ---------------------------

    def _derive_snapshot_id(self, **kwargs: Any) -> str:
        return derive_census_snapshot_id(
            profile_id=kwargs["profile_id"],
            captured_at=kwargs["captured_at"],
            source_url=kwargs["source_url"],
            census_facts=kwargs["census_facts"],
        )

    def _build_active_payload(self, *, snapshot_id: str, **kwargs: Any) -> CensusSnapshot:
        return CensusSnapshot(
            snapshot_id=snapshot_id,
            bucket_id=self._repository.bucket_id,
            profile_id=kwargs["profile_id"].strip(),
            captured_at=kwargs["captured_at"],
            source_url=kwargs["source_url"],
            state=SnapshotLifecycleState.ACTIVE,
            census_facts=dict(kwargs["census_facts"]),
        )

    def _payload_axis_key(self, payload: CensusSnapshot) -> tuple[Any, ...]:
        return (payload.profile_id,)

    def _payload_captured_at(self, payload: CensusSnapshot) -> datetime:
        return payload.captured_at

    def _payload_snapshot_id(self, payload: CensusSnapshot) -> str:
        return payload.snapshot_id

    def _payload_state(self, payload: CensusSnapshot) -> SnapshotLifecycleState:
        return payload.state

    def _demote_to_superseded(
        self, payload: CensusSnapshot, *, superseded_by: str
    ) -> CensusSnapshot:
        return payload.model_copy(
            update={
                "state": SnapshotLifecycleState.SUPERSEDED,
                "superseded_by_snapshot_id": superseded_by,
            }
        )


__all__ = [
    "CENSUS_SNAPSHOT_NAMESPACE",
    "CensusSnapshot",
    "CensusSnapshotRepository",
    "CensusSnapshotService",
    "CensusSnapshotState",
    "census_snapshot_object_key",
    "derive_census_snapshot_id",
]
