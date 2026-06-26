"""Application-live persistence for captured AEAT justificante receipts.

The live justificante pull retrieves the authentic, AEAT-signed
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
at FINANCIAL sensitivity under the justificante-capture namespace, and records
each capture as a lifecycle event via :class:`BucketEventHistoryRepository`.

The captured PDF bytes ride inside the encrypted snapshot :class:`Envelope`
as a base64 ``str`` (binary cannot survive the JSON envelope verbatim); the
raw-bytes ``pdf_sha256`` is the content address used for snapshot-id
derivation and dedup.
"""

from __future__ import annotations

import base64
import binascii
from collections.abc import Sequence
from datetime import datetime
from typing import TYPE_CHECKING, Any, override

from pydantic import BaseModel, Field, field_validator, model_validator

if TYPE_CHECKING:
    from ...adapters.outbound.aeat.sede import Declaracion, Expediente
    from ...domain.justificante import Justificante
    from ...domain.modelos import ModeloRecord
    from ..modelo import ModeloReconciliationReport

from ...adapters.persistence.storage import (
    LIVE_JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE as JUSTIFICANTE_CAPTURE_STORAGE_NAMESPACE,
)
from ...adapters.persistence.storage import (
    Envelope,
)
from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import Modelo, Period
from ...core.external_constants import UTF_8_ENCODING
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
    period: Period
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
            raise LiveApplicationInputError(
                f"justificante capture modelo {value!r} is not a known AEAT modelo",
            ) from exc
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
    period: Period,
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
            "period": period.registry_token,
            "pdf_sha256": pdf_sha256,
        },
    )


def resolve_period_expediente(
    *,
    declarations: Sequence[Declaracion],
    expedientes: Sequence[Expediente],
    modelo: str,
    period: Period,
) -> Expediente:
    """Resolve the capturable expediente for one ``(modelo, period)`` filing.

    The procedure-tree :class:`Expediente` carries no period, so for a
    multi-period modelo (quarterly 1T-4T) it cannot disambiguate which
    quarter's receipt to pull. The period-bearing surface is the filed
    *declarations register* (:class:`Declaracion` carries ``period`` and
    ``expediente_id``). This resolver picks the declaration matching the
    target ``(modelo, period)`` (the latest filing for that period when a
    period was re-filed), then cross-references its ``expediente_id`` against
    the tree to return the capturable expediente. It NEVER returns a
    different period's expediente: a missing or unmatched declaration raises
    rather than falling back to a wrong-quarter receipt.

    The within-period tiebreak ranks the accepted (``ALTA``) declaration ahead
    of ``presented_at``, matching the two sibling period-resolution surfaces
    (``latest_declarations_by_period`` and the sede walker's latest-selection),
    so a later cancellation / correction row (a non-``ALTA`` ``estado`` such as
    ``Anulada`` or ``Baja``) presented after the accepted filing does not win
    and pull the wrong-state receipt.

    Raises:
        LiveApplicationInputError: when no declaration matches the requested
            period, or the matched declaration's expediente is absent from
            the tree.
    """
    target_period = period.registry_token
    candidates = [
        declaration for declaration in declarations if declaration.modelo == modelo and declaration.period == period
    ]
    if not candidates:
        raise LiveApplicationInputError(
            f"no filed declaration for modelo={modelo!r} period={target_period!r}; "
            "cannot resolve a justificante expediente for this period",
        )
    chosen = max(
        candidates,
        key=lambda declaration: (
            declaration.estado.upper() == "ALTA",
            declaration.presented_at,
            declaration.expediente_id,
        ),
    )
    for expediente in expedientes:
        if expediente.expediente_id == chosen.expediente_id:
            return expediente
    raise LiveApplicationInputError(
        f"declaration for modelo={modelo!r} period={target_period!r} references expediente "
        f"{chosen.expediente_id!r} which is not present in the expedientes tree",
    )


class JustificanteCaptureSnapshotRepository:
    """Secure-DB repository for captured justificante snapshots in one bucket.

    Composes the shared :class:`SecureSnapshotRepository` for the read surface
    (load / resolve / list / exists), preserving the class identity,
    ``JustificanteCaptureSnapshotNotFoundError`` messages, and the
    ``captured_at`` list ordering. ``save`` is kept local because justificante
    stamps the envelope ``written_at`` with the capture time (not ``now()``),
    a deliberate divergence from the shared base.
    """

    def __init__(self, *, bucket_id: str, objects: SecureObjectRepository | None = None) -> None:
        trimmed = bucket_id.strip()
        if not trimmed:
            raise LiveApplicationInputError("bucket_id must not be blank")
        self._bucket_id = trimmed
        self._objects = objects if objects is not None else secure_object_repository_for_bucket(trimmed)
        self._delegate: SecureSnapshotRepository[JustificanteCaptureSnapshot] = SecureSnapshotRepository(
            bucket_id=trimmed,
            payload_model=JustificanteCaptureSnapshot,
            namespace_definition=JUSTIFICANTE_CAPTURE_STORAGE_NAMESPACE,
            object_key=justificante_capture_snapshot_object_key,
            not_found_factory=lambda snapshot_id: JustificanteCaptureSnapshotNotFoundError(
                f"justificante capture snapshot {snapshot_id!r} not found in bucket {trimmed!r}",
                suggestion="aeat app live justificante list",
            ),
            ambiguous_prefix_factory=lambda snapshot_id, _full_ids: JustificanteCaptureSnapshotNotFoundError(
                f"justificante capture snapshot prefix {snapshot_id!r} is ambiguous",
                suggestion="provide a longer snapshot id",
            ),
            domain_label="justificante capture",
            objects=self._objects,
        )

    @property
    def bucket_id(self) -> str:
        return self._bucket_id

    def exists(self, snapshot_id: str) -> bool:
        return self._delegate.exists(snapshot_id)

    def load(self, snapshot_id: str) -> JustificanteCaptureSnapshot:
        return self._delegate.load(snapshot_id)

    def list_snapshots(self) -> tuple[JustificanteCaptureSnapshot, ...]:
        return tuple(
            sorted(self._delegate.list_snapshots(), key=lambda item: (item.captured_at, item.snapshot_id)),
        )

    def resolve(self, snapshot_id: str) -> JustificanteCaptureSnapshot:
        return self._delegate.resolve(snapshot_id)

    def save(self, snapshot: JustificanteCaptureSnapshot) -> None:
        if snapshot.bucket_id != self._bucket_id:
            raise LiveApplicationInputError(
                f"justificante capture snapshot bucket_id={snapshot.bucket_id!r} "
                f"does not match repository bucket {self._bucket_id!r}",
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
            payload=envelope.model_dump_json().encode(UTF_8_ENCODING),
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
        period: Period,
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
        period: Period,
    ) -> JustificanteCaptureSnapshot | None:
        snapshots = [
            snapshot
            for snapshot in self.list_snapshots(filing_year=filing_year)
            if snapshot.modelo == modelo and snapshot.period == period
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
            period=kwargs["period"],
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
            },
        )


def parse_capture_to_justificante(snapshot: JustificanteCaptureSnapshot) -> Justificante:
    """Parse a persisted capture's PDF into a strict domain :class:`Justificante`.

    Reads the encrypted snapshot's bytes in memory and runs the inbound parser.
    Used to register the captured receipt as official filing evidence and to
    reconcile against it.
    """
    from ...adapters.inbound.justificante import parse_justificante_bytes

    return parse_justificante_bytes(snapshot.decoded_pdf_bytes())


def register_capture_justificante_metadata(
    *,
    snapshot: JustificanteCaptureSnapshot,
) -> Justificante | None:
    """Persist parsed justificante metadata for a live capture.

    This records the official AEAT receipt metadata even when the local app has
    no current ``ModeloRecord`` for the period. It does not stamp or create a
    local filing row; that remains owned by
    :func:`register_capture_as_filing_evidence`.

    Returns the persisted :class:`Justificante`, or ``None`` when the captured
    snapshot cannot be parsed into one.
    """
    from ...domain.justificante import JustificanteParseError, JustificanteRepository

    if snapshot.state is not SnapshotLifecycleState.ACTIVE:
        raise LiveApplicationInputError(
            f"cannot register justificante metadata from {snapshot.state.value} "
            f"live-capture snapshot {snapshot.snapshot_id!r}",
        )
    try:
        justificante = parse_capture_to_justificante(snapshot)
    except JustificanteParseError:
        return None
    if justificante.csv.strip().upper() != snapshot.csv.strip().upper():
        raise LiveApplicationInputError(
            f"captured justificante csv {justificante.csv!r} does not match live snapshot csv {snapshot.csv!r}",
        )
    if not _justificante_matches_capture_axis(justificante, snapshot):
        raise LiveApplicationInputError(
            f"captured justificante {snapshot.csv!r} does not match live snapshot axis "
            f"for modelo={snapshot.modelo!r} period={snapshot.period!s}",
        )
    JustificanteRepository().save(justificante)
    return justificante


def reconcile_capture(
    *,
    work_unit_id: str,
    snapshot: JustificanteCaptureSnapshot,
    actor: str = "operator",
) -> ModeloReconciliationReport:
    """Reconcile a work unit against a persisted live capture.

    Reads the captured PDF from secure storage into memory and delegates to the
    existing local-only reconciler; the reconciler never contacts AEAT and never
    writes the plaintext receipt to disk. This is the live-sourced equivalent of
    the operator hand-passing a downloaded justificante via the local
    ``reconcile file --file PATH`` surface.
    """
    from ..modelo import (
        ModeloReconciliationBytesCommand,
        ModeloReconciliationEvidenceKind,
        modelo_reconcile_bytes,
    )

    return modelo_reconcile_bytes(
        ModeloReconciliationBytesCommand(
            work_unit_id=work_unit_id,
            source_kind=ModeloReconciliationEvidenceKind.JUSTIFICANTE,
            source_bytes=snapshot.decoded_pdf_bytes(),
            source_ref=_capture_secure_reference(snapshot),
            actor=actor,
        ),
    )


def _justificante_matches_capture_axis(
    justificante: Justificante,
    snapshot: JustificanteCaptureSnapshot,
) -> bool:
    return (
        justificante.modelo.strip() == snapshot.modelo
        and str(justificante.ejercicio or "").strip() == str(snapshot.filing_year)
        and justificante.period == snapshot.period
    )


def _capture_secure_reference(snapshot: JustificanteCaptureSnapshot) -> str:
    return f"secure-object://{JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE}/{snapshot.snapshot_id}"


def register_capture_as_filing_evidence(
    *,
    snapshot: JustificanteCaptureSnapshot,
) -> ModeloRecord:
    """Stamp a persisted live capture as official evidence on its filing record.

    Loads the work unit's current filing record first; with one present, parses
    the captured receipt into a domain ``Justificante`` (keyed by the capture's
    CSV, which is the gate's evidence reference), registers it, and updates the
    filing record to carry ``AEAT_LIVE_CAPTURE`` external evidence referencing
    it. After this, the cross-period clean-state gate's
    ``MISSING_JUSTIFICANTE_VERIFICATION`` blocker clears for the period, because
    ``aeat_live_capture`` is a justificante-verified evidence kind and the
    referenced justificante record loads. Emits a
    ``MODELO_LIVE_EVIDENCE_STAMPED`` bucket event recording the action.

    Returns the stamped :class:`~aeat.domain.modelos.ModeloRecord`.

    Raises:
        LiveApplicationInputError: when no current filing record exists for the
            captured ``(modelo, filing_year, period)`` — the operator must file
            the period before attaching live-capture evidence to it.
    """
    from ...core.time import now
    from ...domain.buckets import (
        BucketEvent,
        BucketEventHistoryRepository,
        BucketEventObjectType,
        BucketEventType,
        append_bucket_event,
        derive_bucket_event_id,
    )
    from ...domain.justificante import JustificanteRepository
    from ...domain.modelos import (
        ExternalEvidence,
        ExternalEvidenceKind,
        ModeloRecordCatalogueRepository,
        upsert_filing_record,
    )

    if snapshot.state is not SnapshotLifecycleState.ACTIVE:
        raise LiveApplicationInputError(
            f"cannot stamp {snapshot.state.value} live-capture snapshot {snapshot.snapshot_id!r} as filing evidence",
        )

    filing_repository = ModeloRecordCatalogueRepository()
    catalogue = filing_repository.load()
    current = catalogue.current_for(
        bucket_id=snapshot.bucket_id,
        modelo=snapshot.modelo,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
    )
    if current is None:
        raise LiveApplicationInputError(
            f"no current filing record for modelo={snapshot.modelo!r} "
            f"period={snapshot.period!s}; "
            "file the period before stamping live-capture evidence",
        )

    justificante = parse_capture_to_justificante(snapshot)
    if justificante.csv.strip().upper() != snapshot.csv.strip().upper():
        raise LiveApplicationInputError(
            f"captured justificante csv {justificante.csv!r} does not match live snapshot csv {snapshot.csv!r}",
        )
    expected_tax_id = _expected_tax_id_for_filing_record(current)
    if not _justificante_matches_filing_record(justificante, current, expected_tax_id=expected_tax_id):
        raise LiveApplicationInputError(
            f"captured justificante {snapshot.csv!r} does not match current filing record "
            f"for modelo={current.modelo!s} period={current.period!s}",
        )
    if current.aeat_accepted and current.external_evidence is not None:
        if _existing_capture_evidence_matches_current_csv(current, snapshot.csv):
            JustificanteRepository().save(justificante)
            return current
        raise LiveApplicationInputError(
            f"cannot overwrite existing AEAT evidence {current.external_evidence.reference_id!r} "
            f"on filing record {current.filing_record_id!r} with live-capture csv {snapshot.csv!r}",
        )
    JustificanteRepository().save(justificante)

    stamped_at = now()
    stamped = current.model_copy(
        update={
            "external_evidence": ExternalEvidence(
                kind=ExternalEvidenceKind.AEAT_LIVE_CAPTURE,
                reference_id=snapshot.csv,
                imported_at=stamped_at,
            ),
            "aeat_accepted": True,
        },
    )
    filing_repository.save(upsert_filing_record(catalogue, stamped))

    event_payload = {
        "work_unit_id": current.work_unit_id,
        "modelo": snapshot.modelo,
        "filing_year": str(snapshot.filing_year),
        "period": snapshot.period.registry_token,
        "evidence_kind": ExternalEvidenceKind.AEAT_LIVE_CAPTURE.value,
        "evidence_reference_id": snapshot.csv,
        "snapshot_id": snapshot.snapshot_id,
    }
    bucket_event_repository = BucketEventHistoryRepository()
    bucket_event_repository.save(
        append_bucket_event(
            bucket_event_repository.load(),
            BucketEvent(
                event_id=derive_bucket_event_id(
                    bucket_id=snapshot.bucket_id,
                    event_type=BucketEventType.MODELO_LIVE_EVIDENCE_STAMPED,
                    occurred_at=stamped_at,
                    actor="aeat-live-capture",
                    object_type=BucketEventObjectType.FILING_RECORD,
                    object_id=stamped.filing_record_id,
                    payload=event_payload,
                ),
                bucket_id=snapshot.bucket_id,
                event_type=BucketEventType.MODELO_LIVE_EVIDENCE_STAMPED,
                occurred_at=stamped_at,
                actor="aeat-live-capture",
                object_type=BucketEventObjectType.FILING_RECORD,
                object_id=stamped.filing_record_id,
                payload_version=1,
                payload=event_payload,
            ),
        ),
    )
    return stamped


def _expected_tax_id_for_filing_record(filing: ModeloRecord) -> str:
    if filing.member_nif is not None and filing.member_nif.strip():
        return filing.member_nif.strip().upper()
    from ...core.errors import AeatError
    from ..user_profile import UserProfileLifecycleRepository, record_to_values

    try:
        record = UserProfileLifecycleRepository(bucket_id=filing.bucket_id).load(filing.bucket_id)
    except (AeatError, OSError) as exc:
        raise LiveApplicationInputError(
            "cannot stamp live-capture evidence without the filing profile tax identity",
        ) from exc
    values = record_to_values(record)
    tax_id = str(values.get("identity.tax_id") or values.get("tax.id") or "").strip().upper()
    if not tax_id:
        raise LiveApplicationInputError(
            "cannot stamp live-capture evidence without the filing profile tax identity",
        )
    return tax_id


def _justificante_matches_filing_record(
    justificante: Justificante,
    filing: ModeloRecord,
    *,
    expected_tax_id: str,
) -> bool:
    return (
        justificante.modelo.strip() == str(filing.modelo)
        and str(justificante.ejercicio or "").strip() == str(filing.filing_year)
        and justificante.period == filing.period
        and justificante.tax_id.strip().upper() == expected_tax_id.strip().upper()
    )


def _existing_capture_evidence_matches_current_csv(filing: ModeloRecord, csv: str) -> bool:
    evidence = filing.external_evidence
    if evidence is None:
        return False
    kind = getattr(evidence.kind, "value", evidence.kind)
    return (
        str(kind) in {"aeat_csv_register", "aeat_justificante_pdf", "aeat_live_capture"}
        and evidence.reference_id.strip().upper() == csv.strip().upper()
    )


def stamp_capture_evidence_if_filed(snapshot: JustificanteCaptureSnapshot) -> ModeloRecord | None:
    """Best-effort variant of :func:`register_capture_as_filing_evidence`.

    Returns the stamped record when the captured period has a current filing
    record, or ``None`` when none exists yet (the snapshot is still persisted;
    the operator can stamp later by filing the period, then re-capturing) or the
    captured PDF is not parseable into a justificante. Used by the capture
    orchestrator so a capture of a period not yet filed in-app does not fail.
    A present-but-conflicting local filing record is not best-effort: identity,
    period, modelo, and existing-evidence conflicts propagate to the caller.
    """
    from ...domain.justificante import JustificanteParseError
    from ...domain.modelos import ModeloRecordCatalogueRepository

    catalogue = ModeloRecordCatalogueRepository().load()
    current = catalogue.current_for(
        bucket_id=snapshot.bucket_id,
        modelo=snapshot.modelo,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
    )
    if current is None:
        return None

    try:
        return register_capture_as_filing_evidence(snapshot=snapshot)
    except JustificanteParseError:
        return None


__all__ = [
    "JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE",
    "JUSTIFICANTE_CAPTURE_SOURCE_KIND",
    "JustificanteCaptureSnapshot",
    "JustificanteCaptureSnapshotNotFoundError",
    "JustificanteCaptureSnapshotRepository",
    "JustificanteCaptureSnapshotService",
    "derive_justificante_capture_snapshot_id",
    "justificante_capture_snapshot_object_key",
    "parse_capture_to_justificante",
    "reconcile_capture",
    "register_capture_as_filing_evidence",
    "register_capture_justificante_metadata",
    "resolve_period_expediente",
    "stamp_capture_evidence_if_filed",
]
