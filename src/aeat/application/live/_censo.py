"""Application-live persistence for captured Modelo 036 censo snapshots.

``CensoSnapshot`` holds the AEAT-side censo facts the operator's
profile must mirror. AEAT is the binding legal source of truth for
censo data; the local profile is a cache that must be kept honest.
Snapshot records are persisted as :class:`Envelope` objects through a
:class:`SecureObjectRepository` at IDENTITY sensitivity under the censo namespace.

The snapshot pattern mirrors :mod:`aeat.application.live._borrador_100`:
content-addressed snapshot ids, encrypted SQLite persistence under a
namespaced secure-object key, and a closed ACTIVE / SUPERSEDED /
DISCARDED state machine. Re-fetch auto-supersedes the prior ACTIVE
snapshot for the same profile.

The CLI-facing ``CensoSyncService`` is the only caller; the
sede G313 adapter populates ``censo_facts`` from the live
Mis Datos Censales endpoint.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any, override

from pydantic import BaseModel, Field, model_validator

from ...adapters.persistence.storage import (
    LIVE_CENSO_SNAPSHOT_NAMESPACE as CENSO_SNAPSHOT_STORAGE_NAMESPACE,
)
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.identity import BucketId
from ...core.time import now
from ._errors import LiveApplicationInputError
from ._snapshot_base import (
    SecureSnapshotRepository,
    SnapshotLifecycleState,
    SnapshotNotFoundError,
    SnapshotService,
    derive_snapshot_id_from_json,
    enforce_snapshot_state_invariants,
)


class CensoSnapshotNotFoundError(SnapshotNotFoundError):
    """Raised when a Modelo 036 censo snapshot lookup misses by id.

    :class:`SnapshotNotFoundError` inherits ``AeatError`` first, so MRO
    routes ``__init__`` through the structured constructor. Listing
    ``AeatError`` explicitly here would violate C3 linearization.
    """


CENSO_SNAPSHOT_NAMESPACE = CENSO_SNAPSHOT_STORAGE_NAMESPACE.namespace

# censo_facts values are always strings: enum values, ISO date strings,
# NIF strings, and decimal-as-string for the vivienda_office m2 inputs.
# A union Decimal | str silently coerces numeric-looking strings (e.g.
# "15") into Decimal on JSON round-trip, breaking equality and the
# typed-distinction operators expect (the elected_withholding_pct enum
# value is "15" not Decimal("15")). The sede HTML extractor produces
# strings; the engine that consumes the snapshot parses the m2 strings
# back to Decimal at calculation time.
type _CensoFactValue = str


class CensoSnapshot(BaseModel):
    """Captured 036 censo facts available to application consumers.

    `censo_facts` is a flat mapping keyed by the dotted schema path
    (e.g. ``censo.activity_start_date``, ``vivienda_office.office_m2``,
    ``contact.fiscal_address_cadastral_reference``). Values are either
    decimal strings (for the raw m2 inputs) or short literals
    (enum values, ISO dates, NIF strings).

    Attributes:
        snapshot_id: Content-addressed SHA-256 hex over
            ``(profile_id, captured_at, source_url, censo_facts)``.
        bucket_id: Active profile bucket id at capture time. Snapshots
            are bucket-scoped so cross-profile leakage is impossible.
        profile_id: Operator profile identifier the snapshot belongs
            to. Carried separately from bucket_id so multi-profile
            buckets remain addressable.
        captured_at: UTC timestamp at which the sede read completed.
        source_url: The G313 sede endpoint the snapshot was extracted
            from. Audited so operators can trace each capture back to
            its AEAT origin.
        state: Lifecycle state from :class:`SnapshotLifecycleState`.
        censo_facts: Flat mapping from dotted schema path to the
            AEAT-side value. The CensoSyncService.compare verb
            walks this mapping against the local profile.
        superseded_by_snapshot_id: Pointer to the snapshot that
            replaced this one. Required when ``state is SUPERSEDED``;
            absent otherwise.
        discarded_at: Timestamp captured when the operator explicitly
            retired the snapshot.
        discarded_by: Actor label captured when the operator explicitly
            retired the snapshot.
        discard_reason: Audit reason captured when the operator explicitly
            retired the snapshot.
    """

    model_config = _STRICT_FROZEN

    snapshot_id: str = Field(min_length=1, max_length=128)
    bucket_id: BucketId
    profile_id: str = Field(min_length=1, max_length=128)
    captured_at: datetime
    source_url: str = Field(min_length=1, max_length=2048)
    state: SnapshotLifecycleState
    censo_facts: Mapping[str, _CensoFactValue] = Field(default_factory=dict)
    superseded_by_snapshot_id: str | None = Field(default=None, min_length=1, max_length=128)
    discarded_at: datetime | None = None
    discarded_by: str = Field(default="", max_length=128)
    discard_reason: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def _enforce_state_payload(self) -> CensoSnapshot:
        enforce_snapshot_state_invariants(
            state=self.state,
            has_supersession_pointer=self.superseded_by_snapshot_id is not None,
            discarded_at=self.discarded_at,
            discarded_by=self.discarded_by,
            discard_reason=self.discard_reason,
        )
        blank_keys = sorted(key for key in self.censo_facts if not key.strip())
        if blank_keys:
            raise LiveApplicationInputError("censo fact keys must not be blank")
        return self


def censo_snapshot_object_key(bucket_id: str, snapshot_id: str) -> str:
    """Return the secure-object key for one bucket's censo snapshot."""
    trimmed_bucket = bucket_id.strip()
    trimmed_snapshot = snapshot_id.strip()
    if not trimmed_bucket:
        raise LiveApplicationInputError("bucket_id must not be blank")
    if not trimmed_snapshot:
        raise LiveApplicationInputError("snapshot_id must not be blank")
    return f"censo-snapshot:{trimmed_bucket}:{trimmed_snapshot}"


def derive_censo_snapshot_id(
    *,
    profile_id: str,
    captured_at: datetime,
    source_url: str,
    censo_facts: Mapping[str, _CensoFactValue],
) -> str:
    """Return the content-addressed id for one censo capture.

    Two structurally identical snapshots (same profile, same captured-
    at instant, same source, same fact values) produce the same id;
    re-saving is then a no-op via ``CensoSnapshotService.refresh``.
    """
    return derive_snapshot_id_from_json(
        {
            "profile_id": profile_id.strip(),
            "captured_at": captured_at.isoformat(),
            "source_url": source_url,
            "censo_facts": dict(sorted(censo_facts.items())),
        },
    )


class CensoSnapshotRepository:
    """Secure-DB repository for captured 036 censo snapshots.

    Composes the shared :class:`SecureSnapshotRepository` (one canonical
    encrypted secure-object snapshot store) instead of re-implementing the
    load / resolve / list / save / exists boilerplate. The public class
    identity, method signatures, ``CensoSnapshotNotFoundError`` messages, and
    ``captured_at`` list ordering are preserved; the backing secure-object
    store is constructed lazily on first use so the repository can be
    instantiated before a runtime bucket is active.
    """

    def __init__(self, *, bucket_id: str, objects: SecureObjectRepository | None = None) -> None:
        trimmed = bucket_id.strip()
        if not trimmed:
            raise LiveApplicationInputError("bucket_id must not be blank")
        self._bucket_id = trimmed
        self._objects = objects
        self._delegate: SecureSnapshotRepository[CensoSnapshot] | None = None

    @property
    def _repo(self) -> SecureSnapshotRepository[CensoSnapshot]:
        if self._delegate is None:
            self._delegate = SecureSnapshotRepository(
                bucket_id=self._bucket_id,
                payload_model=CensoSnapshot,
                namespace_definition=CENSO_SNAPSHOT_STORAGE_NAMESPACE,
                object_key=censo_snapshot_object_key,
                not_found_factory=lambda snapshot_id: CensoSnapshotNotFoundError(
                    f"censo snapshot {snapshot_id!r} not found in bucket {self._bucket_id!r}",
                    suggestion="aeat config profile censo pull",
                ),
                ambiguous_prefix_factory=lambda snapshot_id, _full_ids: CensoSnapshotNotFoundError(
                    f"censo snapshot prefix {snapshot_id!r} is ambiguous",
                    suggestion="provide a longer snapshot id",
                ),
                domain_label="censo",
                objects=self._objects,
            )
        return self._delegate

    @property
    def bucket_id(self) -> str:
        """Return the profile bucket this repository is scoped to."""
        return self._bucket_id

    def exists(self, snapshot_id: str) -> bool:
        """Report whether a censo snapshot is persisted under the given id."""
        return self._repo.exists(snapshot_id)

    def load(self, snapshot_id: str) -> CensoSnapshot:
        """Load and return the censo snapshot stored under ``snapshot_id``."""
        return self._repo.load(snapshot_id)

    def list_snapshots(self) -> tuple[CensoSnapshot, ...]:
        """Return every censo snapshot for this bucket, oldest capture first."""
        return tuple(
            sorted(self._repo.list_snapshots(), key=lambda item: (item.captured_at, item.snapshot_id)),
        )

    def resolve(self, snapshot_id: str) -> CensoSnapshot:
        """Resolve an exact or unambiguous-prefix snapshot id to a single snapshot."""
        return self._repo.resolve(snapshot_id)

    def save(self, snapshot: CensoSnapshot) -> None:
        """Persist a censo snapshot into this bucket's secure-object store."""
        self._repo.save(snapshot)


class CensoSnapshotService(SnapshotService[CensoSnapshot]):
    """Canonical backend service for bucket-scoped 036 censo snapshots.

    Mirrors :class:`Borrador100SnapshotService`. The CLI's
    `CensoSyncService.refresh_censo` is the only caller of
    :meth:`capture`; `show_censo` reads via :meth:`latest_active`
    and ``resolve_snapshot``; `apply_censo_to_profile` reads
    via :meth:`latest_active`.

    The caller is responsible for emitting the
    `CENSO_REFRESHED` bucket event after a successful capture (the
    snapshot service itself is intentionally event-free so the same
    machinery can be exercised from test scaffolding without
    polluting the bucket-event-history catalogue).
    """

    def __init__(
        self,
        *,
        bucket_id: str,
        repository: CensoSnapshotRepository | None = None,
    ) -> None:
        resolved_repository = repository or CensoSnapshotRepository(bucket_id=bucket_id)
        super().__init__(bucket_id=bucket_id, repository=resolved_repository)

    # ---- public API (signatures unchanged for external callers) ----------

    def capture(
        self,
        *,
        profile_id: str,
        captured_at: datetime,
        source_url: str,
        censo_facts: Mapping[str, _CensoFactValue],
    ) -> CensoSnapshot:
        """Persist a new censo snapshot and return the :class:`CensoSnapshot`; auto-supersedes the prior ACTIVE.

        Re-capturing structurally identical facts (same profile / time /
        source / values) is a no-op: the existing snapshot is loaded
        and returned without supersession.
        """
        return self._capture_with_lifecycle(
            profile_id=profile_id,
            captured_at=captured_at,
            source_url=source_url,
            censo_facts=censo_facts,
        )

    @override
    # TYPE-IGNORE-RATIONALE-OVERRIDE-COVARIANT-RETURN:
    # Subclass returns a narrower snapshot type and adds optional filter params;
    # base-class signature widening would ripple to N subclasses.
    def list_snapshots(  # type: ignore[override]
        self,
        *,
        profile_id: str | None = None,
        state: SnapshotLifecycleState | None = SnapshotLifecycleState.ACTIVE,
    ) -> tuple[CensoSnapshot, ...]:
        """Return censo snapshots for this bucket, narrowed by profile and state.

        Widens the base service's listing with two optional filters. Each
        snapshot moves through a closed lifecycle of ACTIVE, SUPERSEDED, then
        DISCARDED states. By default only ACTIVE snapshots are returned, since
        re-fetching supersedes the prior capture for the same profile.

        Args:
            profile_id: When given, keep only snapshots for this operator
                profile (matched against the trimmed id).
            state: Lifecycle state to keep; defaults to
                ``SnapshotLifecycleState.ACTIVE``. Pass ``None`` to keep
                snapshots in every state.

        Returns:
            tuple[:class:`CensoSnapshot`, ...]: Oldest capture first.
        """
        snapshots: tuple[CensoSnapshot, ...] = super().list_snapshots()
        if profile_id is not None:
            trimmed = profile_id.strip()
            snapshots = tuple(snapshot for snapshot in snapshots if snapshot.profile_id == trimmed)
        if state is not None:
            snapshots = tuple(snapshot for snapshot in snapshots if snapshot.state is state)
        return snapshots

    def latest_active(self, *, profile_id: str) -> CensoSnapshot | None:
        """Return the most recently captured ACTIVE snapshot for a profile.

        Serves the ``show_censo`` and ``apply_censo_to_profile`` CLI verbs,
        which need the single current view of an operator's Modelo 036 census
        facts. Selects the ACTIVE snapshot with the latest ``captured_at`` for
        the given profile.

        Args:
            profile_id: Operator profile whose latest capture is wanted.

        Returns:
            :class:`CensoSnapshot`: The newest ACTIVE snapshot, or ``None`` when the profile
            has no ACTIVE snapshot.
        """
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
    ) -> CensoSnapshot:
        """Mark a snapshot as DISCARDED and return the updated :class:`CensoSnapshot`. Local-only; never contacts AEAT.

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
                "discarded_at": now(),
                "discarded_by": trimmed_actor,
                "discard_reason": discard_reason.strip(),
                "superseded_by_snapshot_id": None,
            },
        )
        self._repository.save(updated)
        return updated

    # ---- SnapshotService[CensoSnapshot] hooks ---------------------------

    @override
    # KWARGS-ANY-RATIONALE-SNAPSHOT-DISPATCH: SnapshotService[T] abstract hook
    # contract uses **kwargs to allow concrete subclasses to accept caller-
    # specific keyword arguments without a shared typed parameter set.
    def _derive_snapshot_id(self, **kwargs: Any) -> str:
        return derive_censo_snapshot_id(
            profile_id=kwargs["profile_id"],
            captured_at=kwargs["captured_at"],
            source_url=kwargs["source_url"],
            censo_facts=kwargs["censo_facts"],
        )

    @override
    # KWARGS-ANY-RATIONALE-SNAPSHOT-PAYLOAD: SnapshotService[T] abstract
    # _build_active_payload hook; concrete subclasses accept caller-specific
    # keyword arguments without a shared typed parameter set.
    def _build_active_payload(self, *, snapshot_id: str, **kwargs: Any) -> CensoSnapshot:
        return CensoSnapshot(
            snapshot_id=snapshot_id,
            bucket_id=self._repository.bucket_id,
            profile_id=kwargs["profile_id"].strip(),
            captured_at=kwargs["captured_at"],
            source_url=kwargs["source_url"],
            state=SnapshotLifecycleState.ACTIVE,
            censo_facts=dict(kwargs["censo_facts"]),
        )

    @override
    def _payload_axis_key(self, payload: CensoSnapshot) -> tuple[Any, ...]:
        return (payload.profile_id,)

    @override
    def _payload_captured_at(self, payload: CensoSnapshot) -> datetime:
        return payload.captured_at

    @override
    def _payload_snapshot_id(self, payload: CensoSnapshot) -> str:
        return payload.snapshot_id

    @override
    def _payload_state(self, payload: CensoSnapshot) -> SnapshotLifecycleState:
        return payload.state

    @override
    def _demote_to_superseded(self, payload: CensoSnapshot, *, superseded_by: str) -> CensoSnapshot:
        return payload.model_copy(
            update={
                "state": SnapshotLifecycleState.SUPERSEDED,
                "superseded_by_snapshot_id": superseded_by,
            },
        )


__all__ = [
    "CENSO_SNAPSHOT_NAMESPACE",
    "CensoSnapshot",
    "CensoSnapshotNotFoundError",
    "CensoSnapshotRepository",
    "CensoSnapshotService",
    "censo_snapshot_object_key",
    "derive_censo_snapshot_id",
]
