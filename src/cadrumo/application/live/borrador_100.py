"""Application-live persistence for captured Modelo 100 borrador snapshots.

Borrador100 is the proof-of-concept consumer of the shared
``_snapshot_base`` lifecycle abstraction. The public exception class names
(``BorradorSnapshotNotFoundError`` on lookup miss,
``LiveApplicationInputError`` on input-validation failures),
``Borrador100SnapshotService`` class identity, storage namespace,
object-key layout, and method signatures are preserved exactly; only
the inline state-machine, supersession, and content-id helpers have
been routed through the shared base.

Snapshot records are wrapped in an
:class:`~cadrumo.adapters.persistence.storage.Envelope` and persisted through a
:class:`~cadrumo.adapters.persistence.storage.SecureObjectRepository` at
``FINANCIAL`` :class:`~cadrumo.adapters.persistence.storage.SensitivityClass`
under the borrador namespace.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import override

from pydantic import BaseModel, Field, model_validator

from ...adapters.persistence.profile.snapshots import SecureSnapshotRepository
from ...adapters.persistence.storage import (
    LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE as BORRADOR_100_SNAPSHOT_STORAGE_NAMESPACE,
)
from ...adapters.persistence.storage import (
    SecureObjectRepository,
)
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import Modelo, Period
from ...core.filing_year import FilingYear
from ...core.hashing import content_hash_hex
from ...core.identity import BucketId, SnapshotId
from ...domain.calculations.registry.ids import BindingId
from .errors import LiveApplicationInputError
from .snapshot_base import (
    SnapshotLifecycleState,
    SnapshotNotFoundError,
    SnapshotService,
    enforce_snapshot_state_invariants,
)

BORRADOR_100_SNAPSHOT_NAMESPACE = BORRADOR_100_SNAPSHOT_STORAGE_NAMESPACE.namespace
type _BorradorValue = Decimal | str


class BorradorSnapshotNotFoundError(SnapshotNotFoundError):
    """Raised when a Modelo 100 borrador snapshot lookup misses by id.

    :class:`SnapshotNotFoundError` inherits ``CadrumoError`` first, so MRO
    routes ``__init__`` through the structured constructor (accepts
    ``context=`` / ``translated_message=`` kwargs) rather than
    :class:`KeyError`'s C-level constructor. Listing ``CadrumoError``
    explicitly here would violate C3 linearization.
    """


class Borrador100Snapshot(BaseModel):
    """Captured Modelo 100 borrador values available to application consumers."""

    model_config = _STRICT_FROZEN

    snapshot_id: SnapshotId
    bucket_id: BucketId
    modelo: str = Field(pattern=f"^{Modelo.M100.value}$")
    filing_year: FilingYear
    period: Period
    captured_at: datetime
    source_url: str = Field(min_length=1, max_length=2048)
    state: SnapshotLifecycleState
    binding_values: Mapping[BindingId, _BorradorValue] = Field(default_factory=dict)
    superseded_by_snapshot_id: SnapshotId | None = None
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
            raise LiveApplicationInputError(
                translated_message="application.live.borrador.errors.binding_value_key_blank",
                context={"blank_key_count": len(blank_keys)},
            )
        return self


def borrador_100_snapshot_object_key(bucket_id: str, snapshot_id: str) -> str:
    """Return the secure-object key for one bucket's Modelo 100 borrador snapshot."""
    trimmed_bucket = bucket_id.strip()
    trimmed_snapshot = snapshot_id.strip()
    if not trimmed_bucket:
        raise LiveApplicationInputError(
            translated_message="application.live.borrador.errors.bucket_id_blank",
        )
    if not trimmed_snapshot:
        raise LiveApplicationInputError(
            translated_message="application.live.borrador.errors.snapshot_id_blank",
        )
    return f"modelo-100-borrador-snapshot:{trimmed_bucket}:{trimmed_snapshot}"


def derive_borrador_100_snapshot_id(
    *,
    filing_year: int,
    period: Period,
    captured_at: datetime,
    source_url: str,
    binding_values: Mapping[BindingId, _BorradorValue],
) -> str:
    """Return the content-addressed id for one Modelo 100 borrador capture.

    The canonical-JSON shape is preserved exactly so existing on-disk
    snapshot ids remain valid: the core canonical JSON hash does not change
    the hashed bytes.
    """
    return content_hash_hex(
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
        """Initialize this public contract."""
        trimmed = bucket_id.strip()
        if not trimmed:
            raise LiveApplicationInputError(
                translated_message="application.live.borrador.errors.bucket_id_blank",
            )
        self._delegate: SecureSnapshotRepository[Borrador100Snapshot] = SecureSnapshotRepository(
            bucket_id=trimmed,
            payload_model=Borrador100Snapshot,
            namespace_definition=BORRADOR_100_SNAPSHOT_STORAGE_NAMESPACE,
            object_key=borrador_100_snapshot_object_key,
            not_found_factory=lambda snapshot_id: BorradorSnapshotNotFoundError(
                translated_message="application.live.borrador.errors.snapshot_not_found",
                context={"snapshot_id": snapshot_id},
            ),
            ambiguous_prefix_factory=lambda snapshot_id, full_ids: BorradorSnapshotNotFoundError(
                translated_message="application.live.borrador.errors.snapshot_prefix_ambiguous",
                context={"snapshot_id": snapshot_id, "match_count": len(full_ids)},
            ),
            domain_label="borrador",
            input_error_cls=LiveApplicationInputError,
            objects=objects,
        )

    @property
    def bucket_id(self) -> str:
        """Execute this public contract operation."""
        return self._delegate.bucket_id

    def exists(self, snapshot_id: str) -> bool:
        """Execute this public contract operation."""
        return self._delegate.exists(snapshot_id)

    def load(self, snapshot_id: str) -> Borrador100Snapshot:
        """Execute this public contract operation."""
        return self._delegate.load(snapshot_id)

    def list_snapshots(self) -> tuple[Borrador100Snapshot, ...]:
        """Execute this public contract operation."""
        return tuple(
            sorted(self._delegate.list_snapshots(), key=lambda item: (item.captured_at, item.snapshot_id)),
        )

    def resolve(self, snapshot_id: str) -> Borrador100Snapshot:
        """Execute this public contract operation."""
        return self._delegate.resolve(snapshot_id)

    def save(self, snapshot: Borrador100Snapshot) -> None:
        """Execute this public contract operation."""
        self._delegate.save(snapshot)


class _Borrador100CaptureRequest(BaseModel):
    model_config = _STRICT_FROZEN

    filing_year: int
    period: Period
    captured_at: datetime
    source_url: str
    binding_values: Mapping[BindingId, _BorradorValue]


class Borrador100SnapshotService(SnapshotService[Borrador100Snapshot, _Borrador100CaptureRequest]):
    """Canonical backend service for bucket-scoped Modelo 100 borrador snapshots."""

    def __init__(
        self,
        *,
        bucket_id: str,
        repository: Borrador100SnapshotRepository | None = None,
    ) -> None:
        """Initialize this public contract."""
        resolved_repository = repository or Borrador100SnapshotRepository(bucket_id=bucket_id)
        super().__init__(bucket_id=bucket_id, repository=resolved_repository)

    def capture(
        self,
        *,
        filing_year: int,
        period: Period,
        captured_at: datetime,
        source_url: str,
        binding_values: Mapping[BindingId, _BorradorValue],
    ) -> Borrador100Snapshot:
        """Execute this public contract operation."""
        return self._capture_with_lifecycle(
            _Borrador100CaptureRequest(
                filing_year=filing_year,
                period=period,
                captured_at=captured_at,
                source_url=source_url,
                binding_values=binding_values,
            ),
        )

    @override
    # TYPE-IGNORE-RATIONALE-OVERRIDE-COVARIANT-RETURN:
    # Subclass returns a narrower snapshot type and adds optional filter params;
    # base-class signature widening would ripple to N subclasses.
    def list_snapshots(
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
        """Execute this public contract operation."""
        return self.resolve_snapshot(snapshot_id)

    def latest_for_year(self, *, filing_year: int, period: Period | None = None) -> Borrador100Snapshot | None:
        """Execute this public contract operation."""
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
    def _derive_snapshot_id(self, capture: _Borrador100CaptureRequest) -> str:
        return derive_borrador_100_snapshot_id(
            filing_year=capture.filing_year,
            period=capture.period,
            captured_at=capture.captured_at,
            source_url=capture.source_url,
            binding_values=capture.binding_values,
        )

    @override
    def _build_active_payload(
        self,
        *,
        snapshot_id: str,
        capture: _Borrador100CaptureRequest,
    ) -> Borrador100Snapshot:
        return Borrador100Snapshot(
            snapshot_id=snapshot_id,
            bucket_id=self._repository.bucket_id,
            modelo=Modelo.M100.value,
            filing_year=capture.filing_year,
            period=capture.period,
            captured_at=capture.captured_at,
            source_url=capture.source_url,
            state=SnapshotLifecycleState.ACTIVE,
            binding_values=dict(capture.binding_values),
        )

    @override
    def _payload_axis_key(self, payload: Borrador100Snapshot) -> tuple[object, ...]:
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
