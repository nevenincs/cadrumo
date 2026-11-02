"""Application-owned Modelo 100 borrador snapshot lifecycle.

Borrador100 is the proof-of-concept consumer of the shared snapshot lifecycle
abstraction. The application owns the payload, identity, state machine, and
repository capability; executable composition supplies the encrypted persistence
implementation through :class:`Borrador100SnapshotRepository`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Protocol, cast, override

from pydantic import BaseModel, Field, PlainSerializer, PlainValidator, StringConstraints, TypeAdapter, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.filing_year import FilingYear
from ...core.hashing import content_hash_hex
from ...core.identity.bucket import BucketId
from ...core.identity.hex_ids import SnapshotId
from ...core.modelo import Modelo
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError, RegistrySnapshotError
from ...domain.calculations.registry.form_codes import form_for_role
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.schema_references import RegistrySnapshotRef
from ..calculations.revision_carry_gate import revision_carry_outcome
from .borrador_100_keys import borrador_keys_not_admitted, require_borrador_keys_admitted
from .errors import LiveApplicationInputError
from .snapshot_base import (
    SnapshotLifecycleState,
    SnapshotNotFoundError,
    SnapshotRepository,
    SnapshotService,
    enforce_snapshot_state_invariants,
)

type _BorradorValue = Decimal | str

_BINDING_ID_ADAPTER: TypeAdapter[BindingId] = TypeAdapter(BindingId)
_KIND_DECIMAL = "decimal"
_KIND_TEXT = "text"


def encode_borrador_binding_values(values: Mapping[BindingId, _BorradorValue]) -> dict[str, dict[str, str]]:
    """Return the stored tagged form of ``values``, ordered by binding id.

    Each value is ``{"kind": "decimal" | "text", "value": <string>}``. A decimal
    keeps its plain-notation string and a text value its exact characters, so
    text such as ``"09"`` and the decimal nine stay distinct once stored.
    """
    encoded: dict[str, dict[str, str]] = {}
    for key, value in sorted(values.items()):
        if isinstance(value, Decimal):
            if not value.is_finite():
                raise ValueError("borrador decimal binding value must be finite")
            encoded[key] = {"kind": _KIND_DECIMAL, "value": format(value, "f")}
        elif isinstance(value, str):
            encoded[key] = {"kind": _KIND_TEXT, "value": value}
        else:
            raise ValueError("borrador binding value must be a decimal or text")
    return encoded


def _decode_borrador_binding_value(raw: object) -> _BorradorValue:
    if isinstance(raw, (Decimal, str)):
        return raw
    if not isinstance(raw, Mapping):
        raise ValueError("borrador binding value must be a tagged decimal or text")
    tagged = cast("Mapping[object, object]", raw)
    text = tagged.get("value")
    if set(tagged) != {"kind", "value"} or not isinstance(text, str):
        raise ValueError("borrador binding value must be a tagged decimal or text")
    kind = tagged["kind"]
    if kind == _KIND_TEXT:
        return text
    if kind == _KIND_DECIMAL:
        try:
            value = Decimal(text)
        except ArithmeticError as exc:
            raise ValueError("borrador decimal binding value is not a decimal") from exc
        if not value.is_finite():
            raise ValueError("borrador decimal binding value must be finite")
        return value
    raise ValueError("borrador binding value kind must be decimal or text")


def _decode_borrador_binding_values(raw: object) -> dict[str, _BorradorValue]:
    if not isinstance(raw, Mapping):
        raise ValueError("borrador binding values must be a mapping")
    entries = cast("Mapping[object, object]", raw)
    return {
        _BINDING_ID_ADAPTER.validate_python(key, strict=True): _decode_borrador_binding_value(value)
        for key, value in entries.items()
    }


type _BorradorBindingValues = Annotated[
    Mapping[BindingId, _BorradorValue],
    PlainValidator(_decode_borrador_binding_values),
    PlainSerializer(encode_borrador_binding_values, when_used="json"),
]


BorradorSourceUrl = Annotated[str, StringConstraints(min_length=1, max_length=2048)]
"""The sede address a borrador snapshot was captured from."""


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
    modelo: str = Field(pattern=f"^{Modelo('100').value}$")
    filing_year: FilingYear
    period: Period
    registry_snapshot_ref: RegistrySnapshotRef
    captured_at: datetime
    source_url: BorradorSourceUrl
    state: SnapshotLifecycleState
    binding_values: _BorradorBindingValues = Field(default_factory=dict)
    superseded_by_snapshot_id: SnapshotId | None = None
    discarded_at: datetime | None = None
    discarded_by: str = Field(default="", max_length=128)
    discard_reason: str = Field(default="", max_length=512)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _enforce_state_payload(self) -> Borrador100Snapshot:
        expected_ref = RegistrySnapshotRef(
            modelo=self.modelo,
            revision_id=self.registry_snapshot_ref.revision_id,
            modelo_year=self.filing_year,
            period=self.period.registry_token,
        )
        if self.registry_snapshot_ref != expected_ref:
            raise ValueError("borrador registry_snapshot_ref must match modelo, filing_year, and period")
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


class Borrador100SnapshotRefusalReason(StrEnum):
    """Why a stored borrador snapshot cannot be read under the pinned authority.

    ``REGISTRY_COORDINATE_UNCONFIRMED`` means the stored registry revision no
    longer re-confirms for its coordinate. ``BINDING_KEYS_NOT_ADMITTED`` means a
    stored key is a free casilla key or a binding the revision does not admit.
    ``COORDINATE_OUTSIDE_SUPPORT`` means the stored filing year lies outside the
    registry support envelope, which resolves no snapshot for it.
    Either way the snapshot is kept as stored and the document has to be
    imported again.
    """

    REGISTRY_COORDINATE_UNCONFIRMED = "registry_coordinate_unconfirmed"
    BINDING_KEYS_NOT_ADMITTED = "binding_keys_not_admitted"
    COORDINATE_OUTSIDE_SUPPORT = "coordinate_outside_support"


Borrador100SnapshotRefusalReasonValue = Literal[
    Borrador100SnapshotRefusalReason.REGISTRY_COORDINATE_UNCONFIRMED,
    Borrador100SnapshotRefusalReason.BINDING_KEYS_NOT_ADMITTED,
    Borrador100SnapshotRefusalReason.COORDINATE_OUTSIDE_SUPPORT,
]
"""The same refusal reasons where a CLI payload must accept the plain token."""


@dataclass(frozen=True, slots=True)
class Borrador100RefusedSnapshot:
    """One stored snapshot a read refused, with the reason it was refused."""

    snapshot: Borrador100Snapshot
    reason: Borrador100SnapshotRefusalReason


@dataclass(frozen=True, slots=True)
class Borrador100SnapshotReading:
    """The snapshots a read admitted and, separately, the ones it refused.

    A refused snapshot is neither dropped nor counted as absent: a reading with
    no admitted snapshot and one refused snapshot is not an empty store.
    ``outdated_stored_snapshots`` counts stored rows written under an older
    storage schema across the whole Borrador 100 store, whatever the year read:
    such a row cannot be decoded, so its year is unknowable, it is counted
    rather than named, and it is not an empty store either.
    """

    readable: tuple[Borrador100Snapshot, ...]
    refused: tuple[Borrador100RefusedSnapshot, ...]
    outdated_stored_snapshots: int = 0


def borrador_100_snapshot_refusal(
    snapshot: Borrador100Snapshot,
    *,
    operation: PinnedAuthorityOperation,
) -> Borrador100SnapshotRefusalReason | None:
    """Return why the pinned authority refuses ``snapshot``, or ``None`` when it reads."""
    if revision_carry_outcome(snapshot.registry_snapshot_ref, operation=operation).refused:
        return Borrador100SnapshotRefusalReason.REGISTRY_COORDINATE_UNCONFIRMED
    try:
        revision = operation.snapshot(
            snapshot.modelo,
            filing_year=snapshot.filing_year,
            period=snapshot.period.registry_token,
        ).revision
    except FilingYearOutsideSupportEnvelopeError:
        return Borrador100SnapshotRefusalReason.COORDINATE_OUTSIDE_SUPPORT
    if borrador_keys_not_admitted(snapshot.binding_values, revision):
        return Borrador100SnapshotRefusalReason.BINDING_KEYS_NOT_ADMITTED
    return None


def require_borrador_100_snapshot_coordinates_current(
    snapshot: Borrador100Snapshot,
    *,
    operation: PinnedAuthorityOperation,
) -> Borrador100Snapshot:
    """Return a persisted borrador only when its coordinate and every stored key re-confirm.

    A key is current only when the pinned revision admits it to a borrador
    snapshot, so a snapshot keyed by free casilla ids or by a binding the
    revision no longer declares is refused rather than read.
    """
    outcome = revision_carry_outcome(snapshot.registry_snapshot_ref, operation=operation)
    if outcome.refused:
        raise RegistrySnapshotError(
            "borrador registry coordinate cannot be re-confirmed: "
            f"{snapshot.registry_snapshot_ref.revision_id}: {outcome.detail}"
        )
    revision = operation.snapshot(
        snapshot.modelo,
        filing_year=snapshot.filing_year,
        period=snapshot.period.registry_token,
    ).revision
    require_borrador_keys_admitted(snapshot.binding_values, revision)
    return snapshot


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
    registry_snapshot_ref: RegistrySnapshotRef,
    source_url: str,
    binding_values: Mapping[BindingId, _BorradorValue],
) -> str:
    """Return the content-addressed id for one Modelo 100 borrador document.

    The id covers what the document says: its coordinate, the pinned registry
    revision, the source (which names the PDF digest for a file import) and the
    projected values. The capture instant is not part of it, so importing the
    same document again resolves to the snapshot already stored.
    """
    if (
        registry_snapshot_ref.modelo != form_for_role("renta.annual")
        or registry_snapshot_ref.modelo_year != filing_year
        or registry_snapshot_ref.period != period.registry_token
    ):
        raise ValueError("borrador snapshot identity coordinate must match registry_snapshot_ref")
    return content_hash_hex(
        {
            "modelo": Modelo("100").value,
            "filing_year": filing_year,
            "period": period.registry_token,
            "registry_snapshot_ref": registry_snapshot_ref.model_dump(mode="json"),
            "source_url": source_url,
            "binding_values": encode_borrador_binding_values(binding_values),
        },
    )


class Borrador100SnapshotRepository(SnapshotRepository[Borrador100Snapshot], Protocol):
    """Application persistence capability for bucket-scoped borrador snapshots.

    Encrypted secure-object storage, namespaces, object keys, and persistence
    errors belong to the outer adapter. Implementations satisfy this structural
    contract without inheriting application code. ``list_snapshots`` returns the
    snapshots stored under the current schema;
    ``list_snapshots_with_outdated_count`` returns the same snapshots with the
    number of rows stored under an older one, read in one pass over the store.
    """

    def list_snapshots_with_outdated_count(self) -> tuple[tuple[Borrador100Snapshot, ...], int]:
        """Return the current-schema snapshots and how many older-schema rows were skipped."""
        ...


class _Borrador100CaptureRequest(BaseModel):
    model_config = _STRICT_FROZEN

    filing_year: int
    period: Period
    registry_snapshot_ref: RegistrySnapshotRef
    captured_at: datetime
    source_url: str
    binding_values: Mapping[BindingId, _BorradorValue]


class Borrador100CaptureOutcome(StrEnum):
    """What one capture call did, so a re-import is never reported as a fresh capture.

    Content identity does not cover the capture instant, so importing a document
    again resolves to the snapshot already stored for it, in whatever state it is.
    """

    CAPTURED = "captured"
    """A new snapshot was stored and is the active one for its year."""
    CAPTURED_SUPERSEDED = "captured_superseded"
    """A new snapshot was stored, but a newer active capture already exists."""
    ALREADY_ACTIVE = "already_active"
    """The document resolved to the stored active snapshot; nothing was written."""
    RESOLVED_SUPERSEDED = "resolved_superseded"
    """The document resolved to a stored superseded snapshot; the active one is unchanged."""
    RESOLVED_DISCARDED = "resolved_discarded"
    """The document resolved to a stored discarded snapshot; nothing was written."""


Borrador100CaptureOutcomeValue = Literal[
    Borrador100CaptureOutcome.CAPTURED,
    Borrador100CaptureOutcome.CAPTURED_SUPERSEDED,
    Borrador100CaptureOutcome.ALREADY_ACTIVE,
    Borrador100CaptureOutcome.RESOLVED_SUPERSEDED,
    Borrador100CaptureOutcome.RESOLVED_DISCARDED,
]
"""The same capture outcomes where a CLI payload must accept the plain token."""


@dataclass(frozen=True, slots=True)
class Borrador100Capture:
    """The snapshot one capture call resolved to and what the call did."""

    snapshot: Borrador100Snapshot
    outcome: Borrador100CaptureOutcome


def _capture_outcome(snapshot: Borrador100Snapshot, *, written: bool) -> Borrador100CaptureOutcome:
    if written:
        if snapshot.state is SnapshotLifecycleState.ACTIVE:
            return Borrador100CaptureOutcome.CAPTURED
        return Borrador100CaptureOutcome.CAPTURED_SUPERSEDED
    if snapshot.state is SnapshotLifecycleState.ACTIVE:
        return Borrador100CaptureOutcome.ALREADY_ACTIVE
    if snapshot.state is SnapshotLifecycleState.SUPERSEDED:
        return Borrador100CaptureOutcome.RESOLVED_SUPERSEDED
    return Borrador100CaptureOutcome.RESOLVED_DISCARDED


class Borrador100SnapshotService(SnapshotService[Borrador100Snapshot, _Borrador100CaptureRequest]):
    """Canonical backend service for bucket-scoped Modelo 100 borrador snapshots."""

    def __init__(
        self,
        *,
        bucket_id: str,
        repository: Borrador100SnapshotRepository,
    ) -> None:
        """Initialize this public contract."""
        super().__init__(bucket_id=bucket_id, repository=repository)
        self._borrador_repository = repository

    def capture(
        self,
        *,
        filing_year: int,
        period: Period,
        captured_at: datetime,
        source_url: str,
        binding_values: Mapping[BindingId, _BorradorValue],
        operation: PinnedAuthorityOperation | None = None,
    ) -> Borrador100Snapshot:
        """Capture one document and return the snapshot it resolved to."""
        return self.capture_with_outcome(
            filing_year=filing_year,
            period=period,
            captured_at=captured_at,
            source_url=source_url,
            binding_values=binding_values,
            operation=operation,
        ).snapshot

    def capture_with_outcome(
        self,
        *,
        filing_year: int,
        period: Period,
        captured_at: datetime,
        source_url: str,
        binding_values: Mapping[BindingId, _BorradorValue],
        operation: PinnedAuthorityOperation | None = None,
    ) -> Borrador100Capture:
        """Capture one document and report whether it was stored or resolved to a stored snapshot.

        Raises:
            LiveApplicationInputError: Before any write, when a key is not a
                binding the pinned revision admits to a borrador snapshot.
        """
        if operation is None:
            with bundled_indexed_authority().operation() as pinned:
                return self.capture_with_outcome(
                    filing_year=filing_year,
                    period=period,
                    captured_at=captured_at,
                    source_url=source_url,
                    binding_values=binding_values,
                    operation=pinned,
                )
        selected = operation.snapshot(
            Modelo("100").value,
            filing_year=filing_year,
            period=period.registry_token,
        )
        request = _Borrador100CaptureRequest(
            filing_year=filing_year,
            period=period,
            registry_snapshot_ref=selected.snapshot_ref,
            captured_at=captured_at,
            source_url=source_url,
            binding_values=binding_values,
        )
        require_borrador_keys_admitted(request.binding_values, selected.revision)
        snapshot, written = self._capture_with_lifecycle_status(request)
        return Borrador100Capture(snapshot=snapshot, outcome=_capture_outcome(snapshot, written=written))

    @override
    # TYPE-IGNORE-RATIONALE-OVERRIDE-COVARIANT-RETURN:
    # Subclass returns a narrower snapshot type and adds optional filter params;
    # base-class signature widening would ripple to N subclasses.
    def list_snapshots(
        self,
        *,
        filing_year: int | None = None,
        state: SnapshotLifecycleState | None = SnapshotLifecycleState.ACTIVE,
        operation: PinnedAuthorityOperation | None = None,
    ) -> tuple[Borrador100Snapshot, ...]:
        if operation is None:
            with bundled_indexed_authority().operation() as pinned:
                return self._list_snapshots_current(operation=pinned, filing_year=filing_year, state=state)
        return self._list_snapshots_current(operation=operation, filing_year=filing_year, state=state)

    def _list_snapshots_current(
        self,
        *,
        operation: PinnedAuthorityOperation,
        filing_year: int | None = None,
        state: SnapshotLifecycleState | None = SnapshotLifecycleState.ACTIVE,
    ) -> tuple[Borrador100Snapshot, ...]:
        return tuple(
            require_borrador_100_snapshot_coordinates_current(snapshot, operation=operation)
            for snapshot in self._selected_snapshots(filing_year=filing_year, state=state)
        )

    def _selected_snapshots(
        self,
        *,
        filing_year: int | None,
        state: SnapshotLifecycleState | None,
    ) -> tuple[Borrador100Snapshot, ...]:
        return self._selected_from(super().list_snapshots(), filing_year=filing_year, state=state)

    @staticmethod
    def _selected_from(
        snapshots: tuple[Borrador100Snapshot, ...],
        *,
        filing_year: int | None,
        state: SnapshotLifecycleState | None,
    ) -> tuple[Borrador100Snapshot, ...]:
        if filing_year is not None:
            snapshots = tuple(snapshot for snapshot in snapshots if snapshot.filing_year == filing_year)
        if state is not None:
            snapshots = tuple(snapshot for snapshot in snapshots if snapshot.state is state)
        return snapshots

    def read_snapshots(
        self,
        *,
        operation: PinnedAuthorityOperation,
        filing_year: int | None = None,
        state: SnapshotLifecycleState | None = SnapshotLifecycleState.ACTIVE,
    ) -> Borrador100SnapshotReading:
        """Read the selected snapshots, keeping each one the pinned authority refuses apart.

        One refused snapshot does not fail the read of the others.
        """
        readable: list[Borrador100Snapshot] = []
        refused: list[Borrador100RefusedSnapshot] = []
        stored, outdated = self._borrador_repository.list_snapshots_with_outdated_count()
        for snapshot in self._selected_from(stored, filing_year=filing_year, state=state):
            reason = borrador_100_snapshot_refusal(snapshot, operation=operation)
            if reason is None:
                readable.append(snapshot)
            else:
                refused.append(Borrador100RefusedSnapshot(snapshot=snapshot, reason=reason))
        return Borrador100SnapshotReading(
            readable=tuple(readable),
            refused=tuple(refused),
            outdated_stored_snapshots=outdated,
        )

    def show(self, snapshot_id: str, *, operation: PinnedAuthorityOperation) -> Borrador100Snapshot:
        """Return one snapshot, refusing it when the pinned authority does not admit it."""
        return require_borrador_100_snapshot_coordinates_current(
            self.resolve_snapshot(snapshot_id), operation=operation
        )

    def read_latest_for_year(
        self,
        *,
        filing_year: int,
        operation: PinnedAuthorityOperation,
        period: Period | None = None,
    ) -> Borrador100SnapshotReading:
        """Return the newest readable active snapshot of a year and every refused active one.

        ``readable`` holds at most the newest admitted snapshot; ``refused``
        keeps each active snapshot of the year the pinned authority refuses.
        """
        reading = self.read_snapshots(filing_year=filing_year, operation=operation)
        readable = [snapshot for snapshot in reading.readable if period is None or snapshot.period == period]
        refused = tuple(item for item in reading.refused if period is None or item.snapshot.period == period)
        latest = () if not readable else (max(readable, key=lambda snapshot: snapshot.captured_at),)
        return Borrador100SnapshotReading(
            readable=latest,
            refused=refused,
            outdated_stored_snapshots=reading.outdated_stored_snapshots,
        )

    # ---- SnapshotService[Borrador100Snapshot] hooks ----------------------

    @override
    def _derive_snapshot_id(self, capture: _Borrador100CaptureRequest) -> str:
        return derive_borrador_100_snapshot_id(
            filing_year=capture.filing_year,
            period=capture.period,
            registry_snapshot_ref=capture.registry_snapshot_ref,
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
            modelo=Modelo("100").value,
            filing_year=capture.filing_year,
            period=capture.period,
            registry_snapshot_ref=capture.registry_snapshot_ref,
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
    "Borrador100Capture",
    "Borrador100CaptureOutcome",
    "Borrador100CaptureOutcomeValue",
    "Borrador100RefusedSnapshot",
    "Borrador100Snapshot",
    "Borrador100SnapshotReading",
    "Borrador100SnapshotRefusalReason",
    "Borrador100SnapshotRefusalReasonValue",
    "Borrador100SnapshotRepository",
    "Borrador100SnapshotService",
    "BorradorSnapshotNotFoundError",
    "borrador_100_snapshot_object_key",
    "borrador_100_snapshot_refusal",
    "derive_borrador_100_snapshot_id",
    "encode_borrador_binding_values",
    "require_borrador_100_snapshot_coordinates_current",
]
