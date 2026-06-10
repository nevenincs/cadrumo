"""Application-live persistence for captured AEAT justificante receipts.

The live justificante capture pulls the authentic, AEAT-signed
*justificante de presentación* PDF for a filed work unit through the
read-only sede surface (``capture_justificante`` →
:class:`~aeat.adapters.outbound.aeat.sede.SedeCapture`) and persists it
as a bucket-scoped, content-addressed secure object. The persisted
artefact is the durable, official evidence the local reconciler reads —
the operator no longer hand-downloads the receipt.

This service is a stateful :class:`SnapshotService` sibling of the
Modelo 100 borrador service: it keys supersession on the
``(modelo, filing_year, period)`` axis so a re-filed period's fresh
capture supersedes the prior ACTIVE one, and it persists each snapshot
through a :class:`~aeat.adapters.persistence.storage.sql.SecureObjectRepository`
at FINANCIAL sensitivity under the justificante-capture namespace.

The captured PDF bytes ride inside the encrypted snapshot envelope as a
base64 ``str`` (binary cannot survive the JSON envelope verbatim); the
raw-bytes ``pdf_sha256`` is the content address used for snapshot-id
derivation and dedup.
"""

from __future__ import annotations

import base64
import binascii
from datetime import datetime
from typing import Any, override

from pydantic import BaseModel, Field, field_validator, model_validator

from ...adapters.persistence.storage import (
    LIVE_JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE as JUSTIFICANTE_CAPTURE_STORAGE_NAMESPACE,
)
from ...adapters.persistence.storage import (
    Envelope,
)
from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError
from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ...adapters.persistence.storage.sql import SecureObjectRecord, SecureObjectRepository
from ...core import Modelo
from ...core._models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.identity import BucketId
from ._errors import LiveApplicationInputError
from ._snapshot_base import (
    SnapshotLifecycleState,
    SnapshotNotFoundError,
    SnapshotService,
    derive_snapshot_id_from_json,
    enforce_snapshot_state_invariants,
)

JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE = JUSTIFICANTE_CAPTURE_STORAGE_NAMESPACE.namespace
_JUSTIFICANTE_CAPTURE_SNAPSHOT_VERSION = JUSTIFICANTE_CAPTURE_STORAGE_NAMESPACE.schema_version
_JUSTIFICANTE_CAPTURE_SNAPSHOT_SENSITIVITY = JUSTIFICANTE_CAPTURE_STORAGE_NAMESPACE.sensitivity

# Official source kind stamped on the captured receipt. Member of the
# cross-period clean-state gate's ``_OFFICIAL_SOURCE_KINDS`` frozenset, so a
# dependent period whose upstream evidence is this capture clears the
# ``MISSING_JUSTIFICANTE_VERIFICATION`` blocker.
JUSTIFICANTE_CAPTURE_SOURCE_KIND = "aeat_sede_live_capture"


class JustificanteCaptureSnapshotNotFoundError(SnapshotNotFoundError):
    """Raised when a live justificante-capture snapshot lookup misses by id."""


class JustificanteCaptureSnapshot(BaseModel):
    """One live-captured AEAT justificante receipt persisted for a bucket.

    Bundles the work-unit axis (``modelo`` / ``filing_year`` / ``period``),
    the sede provenance (``expediente_id`` / ``csv``), the content address
    (``pdf_sha256`` over the raw bytes), and the receipt itself
    (``pdf_base64``). The official ``source_kind`` records that the receipt
    came from an authenticated live capture.
    """

    model_config = _STRICT_FROZEN

    snapshot_id: str = Field(min_length=1, max_length=128)
    bucket_id: BucketId
    modelo: str = Field(min_length=1, max_length=16)
    filing_year: int = Field(ge=1900, le=9999)
    period: str = Field(min_length=1, max_length=16)
    expediente_id: str = Field(min_length=12, max_length=32)
    csv: str = Field(min_length=8, max_length=32)
    pdf_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    pdf_base64: str = Field(min_length=1)
    source_kind: str = Field(default=JUSTIFICANTE_CAPTURE_SOURCE_KIND, min_length=1, max_length=64)
    captured_at: datetime
    state: SnapshotLifecycleState
    superseded_by_snapshot_id: str | None = Field(default=None, min_length=1, max_length=128)
    discarded_at: datetime | None = None
    discarded_by: str = Field(default="", max_length=128)
    discard_reason: str = Field(default="", max_length=500)

    @field_validator("modelo")
    @classmethod
    def _modelo_is_known(cls, value: str) -> str:
        """Reject a modelo code that is not a member of the core :class:`Modelo` enum."""
        try:
            Modelo(value)
        except ValueError as exc:
            raise LiveApplicationInputError(f"justificante capture modelo {value!r} is not a known AEAT modelo") from exc
        return value

    @model_validator(mode="after")
    def _enforce_state_payload(self) -> JustificanteCaptureSnapshot:
        enforce_snapshot_state_invariants(
            state=self.state,
            has_supersession_pointer=self.superseded_by_snapshot_id is not None,
            discarded_at=self.discarded_at,
            discarded_by=self.discarded_by,
            discard_reason=self.discard_reason,
        )
        try:
            decoded = base64.b64decode(self.pdf_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise LiveApplicationInputError("justificante capture pdf_base64 is not valid base64") from exc
        if not decoded:
            raise LiveApplicationInputError("justificante capture pdf_base64 must decode to non-empty bytes")
        return self

    def decoded_pdf_bytes(self) -> bytes:
        """Return the raw PDF bytes decoded from :attr:`pdf_base64`."""
        return base64.b64decode(self.pdf_base64, validate=True)


def justificante_capture_snapshot_object_key(bucket_id: str, snapshot_id: str) -> str:
    """Return the secure-object key for one bucket's justificante-capture snapshot."""
    trimmed_bucket = bucket_id.strip()
    trimmed_snapshot = snapshot_id.strip()
    if not trimmed_bucket:
        raise LiveApplicationInputError("bucket_id must not be blank")
    if not trimmed_snapshot:
        raise LiveApplicationInputError("snapshot_id must not be blank")
    return f"justificante-capture-snapshot:{trimmed_bucket}:{trimmed_snapshot}"


def derive_justificante_capture_snapshot_id(
    *,
    modelo: str,
    filing_year: int,
    period: str,
    pdf_sha256: str,
) -> str:
    """Return the content-addressed id for one justificante capture.

    The id is derived from the work-unit axis plus the raw-PDF content
    address, so re-capturing the identical receipt is idempotent while a
    re-filed period (a different signed PDF) yields a new id that
    supersedes the prior ACTIVE snapshot on the same axis.
    """
    return derive_snapshot_id_from_json(
        {
            "modelo": modelo,
            "filing_year": filing_year,
            "period": period.strip(),
            "pdf_sha256": pdf_sha256,
        }
    )


def _snapshot_from_record(
    record: SecureObjectRecord,
    requested_snapshot_id: str | None = None,
) -> JustificanteCaptureSnapshot:
    envelope = Envelope[JustificanteCaptureSnapshot].model_validate_json(record.payload.decode("utf-8"))
    if envelope.classification is not _JUSTIFICANTE_CAPTURE_SNAPSHOT_SENSITIVITY:
        snapshot_label = requested_snapshot_id or envelope.payload.snapshot_id
        raise ClassificationError(
            f"justificante capture snapshot {snapshot_label!r} has classification {envelope.classification}; "
            f"consumer expected {_JUSTIFICANTE_CAPTURE_SNAPSHOT_SENSITIVITY}",
        )
    if envelope.schema_version > _JUSTIFICANTE_CAPTURE_SNAPSHOT_VERSION:
        snapshot_label = requested_snapshot_id or envelope.payload.snapshot_id
        raise EnvelopeVersionError(
            f"justificante capture snapshot {snapshot_label!r} is at version {envelope.schema_version}; "
            f"consumer supports up to {_JUSTIFICANTE_CAPTURE_SNAPSHOT_VERSION}",
        )
    return envelope.payload


class JustificanteCaptureSnapshotRepository:
    """Secure-DB repository for captured justificante snapshots in one bucket."""

    def __init__(self, *, bucket_id: str, objects: SecureObjectRepository | None = None) -> None:
        self._bucket_id = bucket_id.strip()
        if not self._bucket_id:
            raise LiveApplicationInputError("bucket_id must not be blank")
        self._objects = objects if objects is not None else secure_object_repository_for_bucket(self._bucket_id)

    @property
    def bucket_id(self) -> str:
        return self._bucket_id

    def exists(self, snapshot_id: str) -> bool:
        return self._objects.exists(
            JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE,
            justificante_capture_snapshot_object_key(self._bucket_id, snapshot_id),
        )

    def load(self, snapshot_id: str) -> JustificanteCaptureSnapshot:
        record = self._objects.load(
            JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE,
            justificante_capture_snapshot_object_key(self._bucket_id, snapshot_id),
            expected_class=_JUSTIFICANTE_CAPTURE_SNAPSHOT_SENSITIVITY,
            max_supported_version=_JUSTIFICANTE_CAPTURE_SNAPSHOT_VERSION,
        )
        if record is None:
            raise JustificanteCaptureSnapshotNotFoundError(
                f"justificante capture snapshot {snapshot_id!r} not found in bucket {self._bucket_id!r}",
                suggestion="aeat app live justificante list",
            )
        snapshot = _snapshot_from_record(record, requested_snapshot_id=snapshot_id)
        if snapshot.bucket_id != self._bucket_id:
            raise LiveApplicationInputError(
                f"justificante capture snapshot payload bucket_id={snapshot.bucket_id!r} "
                f"does not match repository bucket {self._bucket_id!r}"
            )
        if snapshot.snapshot_id != snapshot_id:
            raise LiveApplicationInputError(
                f"justificante capture snapshot payload id={snapshot.snapshot_id!r} "
                f"does not match requested snapshot {snapshot_id!r}"
            )
        return snapshot

    def list_snapshots(self) -> tuple[JustificanteCaptureSnapshot, ...]:
        snapshots = [
            snapshot
            for record in self._objects.list_records(
                JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE,
                expected_class=_JUSTIFICANTE_CAPTURE_SNAPSHOT_SENSITIVITY,
                max_supported_version=_JUSTIFICANTE_CAPTURE_SNAPSHOT_VERSION,
            )
            for snapshot in (_snapshot_from_record(record),)
            if snapshot.bucket_id == self._bucket_id
        ]
        return tuple(sorted(snapshots, key=lambda item: (item.captured_at, item.snapshot_id)))

    def resolve(self, snapshot_id: str) -> JustificanteCaptureSnapshot:
        trimmed_snapshot_id = snapshot_id.strip()
        if not trimmed_snapshot_id:
            raise LiveApplicationInputError("snapshot_id must not be blank")
        matches = [
            snapshot
            for snapshot in self.list_snapshots()
            if snapshot.snapshot_id == trimmed_snapshot_id or snapshot.snapshot_id.startswith(trimmed_snapshot_id)
        ]
        if not matches:
            raise JustificanteCaptureSnapshotNotFoundError(
                f"justificante capture snapshot {snapshot_id!r} not found in bucket {self._bucket_id!r}",
                suggestion="aeat app live justificante list",
            )
        if len(matches) > 1:
            raise JustificanteCaptureSnapshotNotFoundError(
                f"justificante capture snapshot prefix {snapshot_id!r} is ambiguous",
                suggestion="provide a longer snapshot id",
            )
        return matches[0]

    def save(self, snapshot: JustificanteCaptureSnapshot) -> None:
        if snapshot.bucket_id != self._bucket_id:
            raise LiveApplicationInputError(
                f"justificante capture snapshot bucket_id={snapshot.bucket_id!r} "
                f"does not match repository bucket {self._bucket_id!r}"
            )
        envelope = Envelope[JustificanteCaptureSnapshot](
            schema_version=_JUSTIFICANTE_CAPTURE_SNAPSHOT_VERSION,
            written_at=snapshot.captured_at,
            classification=_JUSTIFICANTE_CAPTURE_SNAPSHOT_SENSITIVITY,
            payload=snapshot,
        )
        self._objects.save(
            namespace=JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE,
            object_key=justificante_capture_snapshot_object_key(self._bucket_id, snapshot.snapshot_id),
            classification=_JUSTIFICANTE_CAPTURE_SNAPSHOT_SENSITIVITY,
            schema_version=_JUSTIFICANTE_CAPTURE_SNAPSHOT_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )


class JustificanteCaptureSnapshotService(SnapshotService[JustificanteCaptureSnapshot]):
    """Canonical backend service for bucket-scoped live justificante captures."""

    def __init__(
        self,
        *,
        bucket_id: str,
        repository: JustificanteCaptureSnapshotRepository | None = None,
    ) -> None:
        resolved_repository = repository or JustificanteCaptureSnapshotRepository(bucket_id=bucket_id)
        super().__init__(bucket_id=bucket_id, repository=resolved_repository)

    # ---- public API ------------------------------------------------------

    def capture(
        self,
        *,
        modelo: str,
        filing_year: int,
        period: str,
        expediente_id: str,
        csv: str,
        pdf_bytes: bytes,
        pdf_sha256: str,
        captured_at: datetime,
    ) -> JustificanteCaptureSnapshot:
        """Persist one captured justificante and return the ACTIVE snapshot.

        Idempotent on the receipt content address: re-capturing the same
        signed PDF returns the existing snapshot. A re-filed period (a new
        signed PDF) supersedes the prior ACTIVE snapshot on the
        ``(modelo, filing_year, period)`` axis.
        """
        return self._capture_with_lifecycle(
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            expediente_id=expediente_id,
            csv=csv,
            pdf_bytes=pdf_bytes,
            pdf_sha256=pdf_sha256,
            captured_at=captured_at,
        )

    @override
    # TYPE-IGNORE-RATIONALE-OVERRIDE-COVARIANT-RETURN:
    # Subclass returns a narrower snapshot type and adds optional filter params;
    # base-class signature widening would ripple to N snapshot subclasses.
    def list_snapshots(  # type: ignore[override]
        self,
        *,
        filing_year: int | None = None,
        state: SnapshotLifecycleState | None = SnapshotLifecycleState.ACTIVE,
    ) -> tuple[JustificanteCaptureSnapshot, ...]:
        snapshots: tuple[JustificanteCaptureSnapshot, ...] = super().list_snapshots()
        if filing_year is not None:
            snapshots = tuple(snapshot for snapshot in snapshots if snapshot.filing_year == filing_year)
        if state is not None:
            snapshots = tuple(snapshot for snapshot in snapshots if snapshot.state is state)
        return snapshots

    def show(self, snapshot_id: str) -> JustificanteCaptureSnapshot:
        return self.resolve_snapshot(snapshot_id)

    def latest_for_work_unit(
        self,
        *,
        modelo: str,
        filing_year: int,
        period: str,
    ) -> JustificanteCaptureSnapshot | None:
        snapshots = [
            snapshot
            for snapshot in self.list_snapshots(filing_year=filing_year)
            if snapshot.modelo == modelo and snapshot.period == period.strip()
        ]
        if not snapshots:
            return None
        return max(snapshots, key=lambda snapshot: snapshot.captured_at)

    # ---- SnapshotService hooks -------------------------------------------

    @override
    # KWARGS-ANY-RATIONALE-SNAPSHOT-DISPATCH: SnapshotService[T] abstract hook
    # contract uses **kwargs to allow concrete subclasses to accept caller-
    # specific keyword arguments without a shared typed parameter set.
    def _derive_snapshot_id(self, **kwargs: Any) -> str:
        return derive_justificante_capture_snapshot_id(
            modelo=kwargs["modelo"],
            filing_year=kwargs["filing_year"],
            period=kwargs["period"],
            pdf_sha256=kwargs["pdf_sha256"],
        )

    @override
    # KWARGS-ANY-RATIONALE-SNAPSHOT-PAYLOAD: SnapshotService[T] abstract
    # _build_active_payload hook carries **kwargs: Any so concrete subclasses
    # accept caller-specific keyword arguments without a shared typed set.
    def _build_active_payload(self, *, snapshot_id: str, **kwargs: Any) -> JustificanteCaptureSnapshot:
        return JustificanteCaptureSnapshot(
            snapshot_id=snapshot_id,
            bucket_id=self._repository.bucket_id,
            modelo=kwargs["modelo"],
            filing_year=kwargs["filing_year"],
            period=kwargs["period"].strip(),
            expediente_id=kwargs["expediente_id"],
            csv=kwargs["csv"],
            pdf_sha256=kwargs["pdf_sha256"],
            pdf_base64=base64.b64encode(kwargs["pdf_bytes"]).decode("ascii"),
            source_kind=JUSTIFICANTE_CAPTURE_SOURCE_KIND,
            captured_at=kwargs["captured_at"],
            state=SnapshotLifecycleState.ACTIVE,
        )

    @override
    def _payload_axis_key(self, payload: JustificanteCaptureSnapshot) -> tuple[Any, ...]:
        return (payload.modelo, payload.filing_year, payload.period)

    @override
    def _payload_captured_at(self, payload: JustificanteCaptureSnapshot) -> datetime:
        return payload.captured_at

    @override
    def _payload_snapshot_id(self, payload: JustificanteCaptureSnapshot) -> str:
        return payload.snapshot_id

    @override
    def _payload_state(self, payload: JustificanteCaptureSnapshot) -> SnapshotLifecycleState:
        return payload.state

    @override
    def _demote_to_superseded(
        self,
        payload: JustificanteCaptureSnapshot,
        *,
        superseded_by: str,
    ) -> JustificanteCaptureSnapshot:
        return payload.model_copy(
            update={
                "state": SnapshotLifecycleState.SUPERSEDED,
                "superseded_by_snapshot_id": superseded_by,
            }
        )


__all__ = [
    "JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE",
    "JUSTIFICANTE_CAPTURE_SOURCE_KIND",
    "JustificanteCaptureSnapshot",
    "JustificanteCaptureSnapshotNotFoundError",
    "JustificanteCaptureSnapshotRepository",
    "JustificanteCaptureSnapshotService",
    "derive_justificante_capture_snapshot_id",
    "justificante_capture_snapshot_object_key",
]
