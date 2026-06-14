"""Application-live persistence for captured Modelo 100 borrador snapshots.

Borrador100 is the proof-of-concept consumer of the shared
``_snapshot_base`` lifecycle abstraction. The public exception class names
(``BorradorSnapshotNotFoundError`` on lookup miss,
``LiveApplicationInputError`` on input-validation failures),
``Borrador100SnapshotService`` class identity, storage namespace,
object-key layout, and method signatures are preserved exactly; only
the inline state-machine, supersession, and content-id helpers have
been routed through the shared base.

Snapshot records are wrapped in an :class:`Envelope` and persisted through a
:class:`SecureObjectRepository` at FINANCIAL sensitivity under the borrador
namespace.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import Any, override

from pydantic import BaseModel, Field, model_validator

from ...adapters.persistence.storage import (
    LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE as BORRADOR_100_SNAPSHOT_STORAGE_NAMESPACE,
)
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import Modelo, Period
from ...core.identity import BucketId
from ._errors import LiveApplicationInputError
from ._snapshot_base import (
    SecureSnapshotRepository,
    SnapshotLifecycleState,
    SnapshotNotFoundError,
    SnapshotService,
    derive_snapshot_id_from_json,
    enforce_snapshot_state_invariants,
)

BORRADOR_100_SNAPSHOT_NAMESPACE = BORRADOR_100_SNAPSHOT_STORAGE_NAMESPACE.namespace
type _BorradorValue = Decimal | str


class BorradorSnapshotNotFoundError(SnapshotNotFoundError):
    """Raised when a Modelo 100 borrador snapshot lookup misses by id.

    :class:`SnapshotNotFoundError` inherits ``AeatError`` first, so MRO
    routes ``__init__`` through the structured constructor (accepts
    ``suggestion=`` / ``context=`` kwargs) rather than
    :class:`KeyError`'s C-level constructor. Listing ``AeatError``
    explicitly here would violate C3 linearization.
    """


class Borrador100Snapshot(BaseModel):
    """Captured Modelo 100 borrador values available to application consumers."""

    model_config = _STRICT_FROZEN

    snapshot_id: str = Field(min_length=1, max_length=128)
    bucket_id: BucketId
    modelo: str = Field(pattern=f"^{Modelo.M100.value}$")
    filing_year: int = Field(ge=1900, le=9999)
    period: Period
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
    period: Period,
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
            "modelo": Modelo.M100.value,
            "filing_year": filing_year,
            "period": period.registry_token,
            "captured_at": captured_at.isoformat(),
            "source_url": source_url,
            "binding_values": {
                key: format(value, "f") if isinstance(value, Decimal) else value
                for key, value in sorted(binding_values.items())
            },
        },
    )


class Borrador100SnapshotRepository:
    """Secure-DB repository for captured Modelo 100 borrador snapshots.

    Composes the shared :class:`SecureSnapshotRepository` (one canonical
    encrypted secure-object snapshot store) rather than re-implementing the
    load / resolve / list / save boilerplate; the public class identity,
    method signatures, and ``BorradorSnapshotNotFoundError`` messages are
    preserved, and ``list_snapshots`` keeps the borrador ``captured_at``
    ordering.
    """

    def __init__(self, *, bucket_id: str, objects: SecureObjectRepository | None = None) -> None:
        trimmed = bucket_id.strip()
        if not trimmed:
            raise LiveApplicationInputError("bucket_id must not be blank")
        self._delegate: SecureSnapshotRepository[Borrador100Snapshot] = SecureSnapshotRepository(
            bucket_id=trimmed,
            payload_model=Borrador100Snapshot,
            namespace_definition=BORRADOR_100_SNAPSHOT_STORAGE_NAMESPACE,
            object_key=borrador_100_snapshot_object_key,
            not_found_factory=lambda snapshot_id: BorradorSnapshotNotFoundError(
                f"borrador snapshot {snapshot_id!r} not found in bucket {trimmed!r}",
                suggestion="aeat app live borrador 100 list",
            ),
            ambiguous_prefix_factory=lambda snapshot_id, _full_ids: BorradorSnapshotNotFoundError(
                f"borrador snapshot prefix {snapshot_id!r} is ambiguous",
                suggestion="provide a longer snapshot id",
            ),
            domain_label="borrador",
            objects=objects,
        )

    @property
    def bucket_id(self) -> str:
        return self._delegate.bucket_id

    def exists(self, snapshot_id: str) -> bool:
        return self._delegate.exists(snapshot_id)

    def load(self, snapshot_id: str) -> Borrador100Snapshot:
        return self._delegate.load(snapshot_id)

    def list_snapshots(self) -> tuple[Borrador100Snapshot, ...]:
        return tuple(
            sorted(self._delegate.list_snapshots(), key=lambda item: (item.captured_at, item.snapshot_id)),
        )

    def resolve(self, snapshot_id: str) -> Borrador100Snapshot:
        return self._delegate.resolve(snapshot_id)

    def save(self, snapshot: Borrador100Snapshot) -> None:
        self._delegate.save(snapshot)


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

    def capture(
        self,
        *,
        filing_year: int,
        period: Period,
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

    @override
    # TYPE-IGNORE-RATIONALE-OVERRIDE-COVARIANT-RETURN:
    # Subclass returns a narrower snapshot type and adds optional filter params;
    # base-class signature widening would ripple to N subclasses.
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

    def latest_for_year(self, *, filing_year: int, period: Period | None = None) -> Borrador100Snapshot | None:
        snapshots = [
            snapshot
            for snapshot in self.list_snapshots(filing_year=filing_year)
            if period is None or snapshot.period == period
        ]
        if not snapshots:
            return None
        return max(snapshots, key=lambda snapshot: snapshot.captured_at)

    # ---- SnapshotService[Borrador100Snapshot] hooks ----------------------

    @override
    # KWARGS-ANY-RATIONALE-SNAPSHOT-DISPATCH: SnapshotService[T] abstract hook
    # contract uses **kwargs to allow concrete subclasses to accept caller-
    # specific keyword arguments without a shared typed parameter set.
    def _derive_snapshot_id(self, **kwargs: Any) -> str:
        return derive_borrador_100_snapshot_id(
            filing_year=kwargs["filing_year"],
            period=kwargs["period"],
            captured_at=kwargs["captured_at"],
            source_url=kwargs["source_url"],
            binding_values=kwargs["binding_values"],
        )

    @override
    # KWARGS-ANY-RATIONALE-SNAPSHOT-PAYLOAD: SnapshotService[T] abstract
    # _build_active_payload hook carries **kwargs: Any so concrete subclasses
    # accept caller-specific keyword arguments without a shared typed set.
    def _build_active_payload(self, *, snapshot_id: str, **kwargs: Any) -> Borrador100Snapshot:
        return Borrador100Snapshot(
            snapshot_id=snapshot_id,
            bucket_id=self._repository.bucket_id,
            modelo=Modelo.M100.value,
            filing_year=kwargs["filing_year"],
            period=kwargs["period"],
            captured_at=kwargs["captured_at"],
            source_url=kwargs["source_url"],
            state=SnapshotLifecycleState.ACTIVE,
            binding_values=dict(kwargs["binding_values"]),
        )

    @override
    def _payload_axis_key(self, payload: Borrador100Snapshot) -> tuple[Any, ...]:
        return (payload.modelo, payload.filing_year, payload.period)

    @override
    def _payload_captured_at(self, payload: Borrador100Snapshot) -> datetime:
        return payload.captured_at

    @override
    def _payload_snapshot_id(self, payload: Borrador100Snapshot) -> str:
        return payload.snapshot_id

    @override
    def _payload_state(self, payload: Borrador100Snapshot) -> SnapshotLifecycleState:
        return payload.state

    @override
    def _demote_to_superseded(self, payload: Borrador100Snapshot, *, superseded_by: str) -> Borrador100Snapshot:
        return payload.model_copy(
            update={
                "state": SnapshotLifecycleState.SUPERSEDED,
                "superseded_by_snapshot_id": superseded_by,
            },
        )


__all__ = [
    "BORRADOR_100_SNAPSHOT_NAMESPACE",
    "Borrador100Snapshot",
    "Borrador100SnapshotRepository",
    "Borrador100SnapshotService",
    "BorradorSnapshotNotFoundError",
    "borrador_100_snapshot_object_key",
    "derive_borrador_100_snapshot_id",
]
