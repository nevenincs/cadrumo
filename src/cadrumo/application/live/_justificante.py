"""Application-live persistence for captured AEAT justificante receipts.

The live justificante pull retrieves the authentic, AEAT-signed
*justificante de presentación* PDF for a filed work unit through the
read-only sede surface (``capture_justificante`` →
:class:`~cadrumo.adapters.outbound.aeat.sede.SedeCapture`) and persists it
as a bucket-scoped, content-addressed secure object. The persisted
artefact is the durable, official evidence the local reconciler reads —
the operator no longer hand-downloads the receipt.

This service is a stateful :class:`SnapshotService` sibling of the
Modelo 100 borrador service: it keys supersession on the
``(modelo, filing_year, period)`` axis so a re-filed period's fresh
capture supersedes the prior ACTIVE one, and it persists each snapshot
through a :class:`~cadrumo.adapters.persistence.storage.SecureObjectRepository`
at FINANCIAL sensitivity under
:data:`cadrumo.adapters.persistence.storage.LIVE_JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE`,
and records each capture as a lifecycle event via
:class:`BucketEventHistoryRepository`.

The captured PDF bytes ride inside the encrypted snapshot :class:`Envelope`
as a base64 ``str`` (binary cannot survive the JSON envelope verbatim); the
raw-bytes ``pdf_sha256`` is the content address used for snapshot-id
derivation and dedup.

See Also:
    :mod:`cadrumo.application.live`
        Public read-only live facade that orchestrates capture and reports
        :class:`~cadrumo.application.live.JustificanteCaptureOutcome`.
    :func:`cadrumo.application.live._filed_observation_persistence.enroll_filed_justificante_evidence`
        Filed-history path that performs the same metadata registration and
        current-record evidence stamping from declaration-register artefacts.
    :mod:`cadrumo.application.overview`
        Calendar projection that reads :class:`JustificanteCaptureSnapshot`
        rows and matching domain justificante metadata as AEAT-side evidence.
    :class:`cadrumo.adapters.persistence.profile.snapshots.SecureSnapshotRepository`
        Shared encrypted snapshot repository used by this bucket-scoped
        capture repository.
    :class:`~cadrumo.domain.modelos.ModeloRecord`
        Local filing record stamped with live
        :class:`~cadrumo.domain.modelos.ExternalEvidence` only after the receipt
        matches the current filing axis.
"""

from __future__ import annotations

import base64
import binascii
from collections.abc import Sequence
from datetime import datetime
from typing import TYPE_CHECKING, override

from pydantic import BaseModel, Field, field_validator, model_validator

if TYPE_CHECKING:
    from ...adapters.outbound.aeat.sede import Declaracion, Expediente
    from ...domain.justificante import Justificante
    from ...domain.modelos import ModeloRecord
    from ..modelo import ModeloReconciliationReport

from ...adapters.persistence.profile.snapshots import SecureSnapshotRepository
from ...adapters.persistence.storage import (
    LIVE_JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE as JUSTIFICANTE_CAPTURE_STORAGE_NAMESPACE,
)
from ...adapters.persistence.storage import (
    Envelope,
    SecureObjectRepository,
    secure_object_repository_for_bucket,
)
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import Modelo, Period, normalise_aeat_csv
from ...core.external_constants import UTF_8_ENCODING
from ...core.hashing import content_hash_hex, sha256_hex
from ...core.identity import AeatCsv, AeatExpedienteId, BucketId, ContentDigest, SnapshotId, tax_id_identity_token
from ..calculations import ObservationSourceKind
from ._errors import (
    LiveApplicationInputError,
    LiveReadPrecondition,
    live_read_no_recovery_verdict,
)
from ._snapshot_base import (
    SnapshotLifecycleState,
    SnapshotNotFoundError,
    SnapshotService,
    enforce_snapshot_state_invariants,
)

JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE = JUSTIFICANTE_CAPTURE_STORAGE_NAMESPACE.namespace
_JUSTIFICANTE_CAPTURE_SNAPSHOT_VERSION = JUSTIFICANTE_CAPTURE_STORAGE_NAMESPACE.schema_version
_JUSTIFICANTE_CAPTURE_SNAPSHOT_SENSITIVITY = JUSTIFICANTE_CAPTURE_STORAGE_NAMESPACE.sensitivity
_LIVE_EVIDENCE_STAMPED_PAYLOAD_VERSION = 2

# Official source kind stamped on the captured receipt. Its explicit
# ``is_official_aeat`` capability lets a dependent period whose upstream evidence
# is this capture clear the ``MISSING_JUSTIFICANTE_VERIFICATION`` blocker.
JUSTIFICANTE_CAPTURE_SOURCE_KIND = ObservationSourceKind.AEAT_SEDE_LIVE_CAPTURE


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

    snapshot_id: SnapshotId
    bucket_id: BucketId
    modelo: str = Field(min_length=1, max_length=16)
    filing_year: int = Field(ge=1900, le=9999)
    period: Period
    expediente_id: AeatExpedienteId
    csv: AeatCsv
    pdf_sha256: ContentDigest
    pdf_base64: str = Field(min_length=1)
    source_kind: ObservationSourceKind = Field(default=JUSTIFICANTE_CAPTURE_SOURCE_KIND)

    @field_validator("source_kind", mode="before")
    @classmethod
    def _parse_source_kind(cls, value: object) -> ObservationSourceKind:
        """Parse persisted snapshot JSON into the closed observation taxonomy."""
        return ObservationSourceKind(value)

    captured_at: datetime
    state: SnapshotLifecycleState
    superseded_by_snapshot_id: SnapshotId | None = None
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
                translated_message="application.live.justificante.errors.modelo_unknown",
                context={"modelo": value},
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
            raise LiveApplicationInputError(
                translated_message="application.live.justificante.errors.pdf_base64_invalid",
                context={"snapshot_id": self.snapshot_id},
            ) from exc
        if not decoded:
            raise LiveApplicationInputError(
                translated_message="application.live.justificante.errors.pdf_base64_empty",
                context={"snapshot_id": self.snapshot_id},
            )
        if sha256_hex(decoded) != self.pdf_sha256:
            raise LiveApplicationInputError(
                translated_message="application.live.justificante.errors.pdf_sha256_mismatch",
                context={"snapshot_id": self.snapshot_id, "decoded_byte_size": len(decoded)},
            )
        return self

    def decoded_pdf_bytes(self) -> bytes:
        """Return the raw PDF bytes decoded from :attr:`pdf_base64`."""
        return base64.b64decode(self.pdf_base64, validate=True)


def justificante_capture_snapshot_object_key(bucket_id: str, snapshot_id: str) -> str:
    """Return the secure-object key for one bucket's justificante-capture snapshot.

    The key shape is the object-key grammar declared by
    :data:`cadrumo.adapters.persistence.storage.LIVE_JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE`.
    """
    trimmed_bucket = bucket_id.strip()
    trimmed_snapshot = snapshot_id.strip()
    if not trimmed_bucket:
        raise LiveApplicationInputError(
            translated_message="application.live.justificante.errors.bucket_id_blank",
        )
    if not trimmed_snapshot:
        raise LiveApplicationInputError(
            translated_message="application.live.justificante.errors.snapshot_id_blank",
        )
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
    return content_hash_hex(
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
            translated_message="application.live.justificante.errors.no_filed_declaration",
            context={"modelo": modelo, "period": target_period},
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
        translated_message="application.live.justificante.errors.expediente_not_in_tree",
        context={
            "modelo": modelo,
            "period": target_period,
            "expediente_id": chosen.expediente_id,
        },
    )


class JustificanteCaptureSnapshotRepository:
    """Secure-DB repository for captured justificante snapshots in one bucket.

    Composes the shared :class:`SecureSnapshotRepository` for the read surface
    (load / resolve / list / exists), preserving the class identity,
    ``JustificanteCaptureSnapshotNotFoundError`` messages, and the
    ``captured_at`` list ordering. ``save`` is kept local because justificante
    stamps the envelope ``written_at`` with the capture time (not ``now()``),
    a deliberate divergence from the shared base.

    The namespace, sensitivity, schema version, and key grammar come from
    :data:`cadrumo.adapters.persistence.storage.LIVE_JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE`.
    Each :class:`JustificanteCaptureSnapshot` is written through an
    :class:`~cadrumo.adapters.persistence.storage.Envelope` so the captured PDF,
    CSV, and expediente metadata stay inside the encrypted
    :class:`~cadrumo.adapters.persistence.storage.SecureObjectRepository`
    bucket store.
    """

    def __init__(self, *, bucket_id: str, objects: SecureObjectRepository | None = None) -> None:
        trimmed = bucket_id.strip()
        if not trimmed:
            raise LiveApplicationInputError(
                translated_message="application.live.justificante.errors.bucket_id_blank",
            )
        self._bucket_id = trimmed
        self._objects = objects if objects is not None else secure_object_repository_for_bucket(trimmed)
        self._delegate: SecureSnapshotRepository[JustificanteCaptureSnapshot] = SecureSnapshotRepository(
            bucket_id=trimmed,
            payload_model=JustificanteCaptureSnapshot,
            namespace_definition=JUSTIFICANTE_CAPTURE_STORAGE_NAMESPACE,
            object_key=justificante_capture_snapshot_object_key,
            not_found_factory=lambda snapshot_id: JustificanteCaptureSnapshotNotFoundError(
                translated_message="application.live.justificante.errors.snapshot_not_found",
                context={"snapshot_id": snapshot_id},
            ),
            ambiguous_prefix_factory=lambda snapshot_id, full_ids: JustificanteCaptureSnapshotNotFoundError(
                translated_message="application.live.justificante.errors.snapshot_prefix_ambiguous",
                context={"snapshot_id": snapshot_id, "match_count": len(full_ids)},
            ),
            domain_label="justificante capture",
            input_error_cls=LiveApplicationInputError,
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
                translated_message="application.live.justificante.errors.snapshot_bucket_mismatch",
                context={
                    "snapshot_bucket_id": snapshot.bucket_id,
                    "repository_bucket_id": self._bucket_id,
                },
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


class _JustificanteCaptureRequest(BaseModel):
    model_config = _STRICT_FROZEN

    modelo: str
    filing_year: int
    period: Period
    expediente_id: AeatExpedienteId
    csv: AeatCsv
    pdf_bytes: bytes
    pdf_sha256: str
    captured_at: datetime


class JustificanteCaptureSnapshotService(
    SnapshotService[JustificanteCaptureSnapshot, _JustificanteCaptureRequest],
):
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
        """Persist one captured justificante and return the ACTIVE :class:`JustificanteCaptureSnapshot`.

        Idempotent on the receipt content address: re-capturing the same
        signed PDF returns the existing snapshot. A re-filed period (a new
        signed PDF) supersedes the prior ACTIVE snapshot on the
        ``(modelo, filing_year, period)`` axis.
        """
        return self._capture_with_lifecycle(
            _JustificanteCaptureRequest(
                modelo=modelo,
                filing_year=filing_year,
                period=period,
                expediente_id=expediente_id,
                csv=csv,
                pdf_bytes=pdf_bytes,
                pdf_sha256=pdf_sha256,
                captured_at=captured_at,
            ),
        )

    @override
    # TYPE-IGNORE-RATIONALE-OVERRIDE-COVARIANT-RETURN:
    # Subclass returns a narrower snapshot type and adds optional filter params;
    # base-class signature widening would ripple to N snapshot subclasses.
    def list_snapshots(
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
    def _derive_snapshot_id(self, capture: _JustificanteCaptureRequest) -> str:
        return derive_justificante_capture_snapshot_id(
            modelo=capture.modelo,
            filing_year=capture.filing_year,
            period=capture.period,
            pdf_sha256=capture.pdf_sha256,
        )

    @override
    def _build_active_payload(
        self,
        *,
        snapshot_id: str,
        capture: _JustificanteCaptureRequest,
    ) -> JustificanteCaptureSnapshot:
        return JustificanteCaptureSnapshot(
            snapshot_id=snapshot_id,
            bucket_id=self._repository.bucket_id,
            modelo=capture.modelo,
            filing_year=capture.filing_year,
            period=capture.period,
            expediente_id=capture.expediente_id,
            csv=capture.csv,
            pdf_sha256=capture.pdf_sha256,
            pdf_base64=base64.b64encode(capture.pdf_bytes).decode("ascii"),
            source_kind=JUSTIFICANTE_CAPTURE_SOURCE_KIND,
            captured_at=capture.captured_at,
            state=SnapshotLifecycleState.ACTIVE,
        )

    @override
    def _payload_axis_key(self, payload: JustificanteCaptureSnapshot) -> tuple[object, ...]:
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


def _require_receipt_csv_matches_capture(
    justificante: Justificante,
    snapshot: JustificanteCaptureSnapshot,
) -> None:
    """Refuse a parsed receipt whose CSV is not the one the capture was fetched under.

    One guard rather than one per caller: the two registration paths asked the
    same question with the same refusal, so a second copy could only drift.
    Both sides go through the shared comparison form, so a receipt whose CSV
    differs only in case or surrounding whitespace is still the same receipt.
    """
    if normalise_aeat_csv(justificante.csv) == normalise_aeat_csv(snapshot.csv):
        return
    raise LiveApplicationInputError(
        translated_message="application.live.justificante.errors.csv_mismatch",
        context={"snapshot_id": snapshot.snapshot_id},
        precondition_verdict=live_read_no_recovery_verdict(
            LiveReadPrecondition.JUSTIFICANTE_MATCHES_CAPTURE,
            facts={"snapshot_id": snapshot.snapshot_id, "csv_matches": False},
        ),
    )


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
    from ...adapters.persistence.profile.justificante import JustificanteRepository
    from ...domain.justificante import JustificanteParseError

    if snapshot.state is not SnapshotLifecycleState.ACTIVE:
        raise LiveApplicationInputError(
            translated_message="application.live.justificante.errors.metadata_snapshot_not_active",
            context={"snapshot_id": snapshot.snapshot_id, "state": snapshot.state.value},
        )
    try:
        justificante = parse_capture_to_justificante(snapshot)
    except JustificanteParseError:
        return None
    _require_receipt_csv_matches_capture(justificante, snapshot)
    if not _justificante_matches_capture_axis(justificante, snapshot):
        raise LiveApplicationInputError(
            translated_message="application.live.justificante.errors.capture_axis_mismatch",
            context={
                "snapshot_id": snapshot.snapshot_id,
                "modelo": snapshot.modelo,
                "period": str(snapshot.period),
            },
            precondition_verdict=live_read_no_recovery_verdict(
                LiveReadPrecondition.JUSTIFICANTE_MATCHES_CAPTURE,
                facts={
                    "snapshot_id": snapshot.snapshot_id,
                    "modelo": snapshot.modelo,
                    "period": str(snapshot.period),
                    "axis_matches": False,
                },
            ),
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

    Returns:
        A :class:`ModeloReconciliationReport` for the in-memory receipt comparison.
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
    return justificante.matches_filing_target(
        modelo=snapshot.modelo,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
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

    Returns the stamped :class:`~cadrumo.domain.modelos.ModeloRecord`.

    Raises:
        LiveApplicationInputError: when no current filing record exists for the
            captured ``(modelo, filing_year, period)`` — the operator must file
            the period before attaching live-capture evidence to it.
    """
    from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ...adapters.persistence.profile.justificante import JustificanteRepository
    from ...adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from ...core.time import now
    from ...domain.buckets import (
        BucketEvent,
        BucketEventObjectType,
        BucketEventType,
        derive_bucket_event_id,
        emit_bucket_events,
    )
    from ...domain.modelos import (
        ExternalEvidence,
        ExternalEvidenceKind,
        upsert_filing_record,
    )

    if snapshot.state is not SnapshotLifecycleState.ACTIVE:
        raise LiveApplicationInputError(
            translated_message="application.live.justificante.errors.evidence_snapshot_not_active",
            context={"snapshot_id": snapshot.snapshot_id, "state": snapshot.state.value},
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
            translated_message="application.live.justificante.errors.filing_record_missing",
            context={"modelo": snapshot.modelo, "period": str(snapshot.period)},
        )

    justificante = parse_capture_to_justificante(snapshot)
    _require_receipt_csv_matches_capture(justificante, snapshot)
    expected_tax_id = _expected_tax_id_for_filing_record(current)
    if not _justificante_matches_filing_record(
        justificante,
        current,
        expected_tax_id=expected_tax_id,
    ):
        raise LiveApplicationInputError(
            translated_message="application.live.justificante.errors.filing_record_mismatch",
            context={
                "snapshot_id": snapshot.snapshot_id,
                "modelo": str(current.modelo),
                "period": str(current.period),
                "filing_record_id": current.filing_record_id,
            },
            precondition_verdict=live_read_no_recovery_verdict(
                LiveReadPrecondition.JUSTIFICANTE_MATCHES_FILING_RECORD,
                facts={
                    "snapshot_id": snapshot.snapshot_id,
                    "modelo": str(current.modelo),
                    "period": str(current.period),
                    "filing_record_id": current.filing_record_id,
                    "matches_filing_record": False,
                },
            ),
        )
    if current.aeat_accepted and current.external_evidence is not None:
        if _existing_capture_evidence_matches_current_csv(current, snapshot.csv):
            JustificanteRepository().save(justificante)
            return current
        raise LiveApplicationInputError(
            translated_message="application.live.justificante.errors.evidence_overwrite_refused",
            context={
                "filing_record_id": current.filing_record_id,
                "snapshot_id": snapshot.snapshot_id,
            },
            precondition_verdict=live_read_no_recovery_verdict(
                LiveReadPrecondition.JUSTIFICANTE_FILING_EVIDENCE_ABSENT,
                facts={
                    "filing_record_id": current.filing_record_id,
                    "snapshot_id": snapshot.snapshot_id,
                    "existing_evidence_present": True,
                },
            ),
        )
    # ORDER IS LOAD-BEARING, and these are separate writes rather than one.
    # The justificante lands BEFORE the filing record cites it, so a failure
    # between them leaves an orphan receipt -- harmless, and re-running restores
    # the pair. The reverse order leaves a filing record carrying
    # AEAT_LIVE_CAPTURE evidence whose justificante does not load, and that
    # record CLEARS the cross-period clean-state gate's missing-justificante
    # blocker on the strength of evidence that is not there. Do not reorder
    # these to read more naturally, and prefer making them one unit of work over
    # swapping them: the sibling linking and reconciliation writers co-commit
    # their two catalogues through the transaction repository's composed write
    # for the same class of reason.
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
        "source_kind": snapshot.source_kind,
        "pdf_sha256": snapshot.pdf_sha256,
        "captured_at": snapshot.captured_at.isoformat(),
        "expediente_id": snapshot.expediente_id,
    }
    # Through the domain emitter, not a local load-append-save: the history is a
    # singleton row, so appending here directly discards an event a concurrent
    # caller wrote, and content-addressed survivors leave no gap to notice it.
    emit_bucket_events(
        repository=BucketEventHistoryRepository(),
        events=(
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
                payload_version=_LIVE_EVIDENCE_STAMPED_PAYLOAD_VERSION,
                payload=event_payload,
            ),
        ),
    )
    return stamped


def _expected_tax_id_for_filing_record(filing: ModeloRecord) -> str:
    if filing.member_nif is not None and filing.member_nif.strip():
        return tax_id_identity_token(filing.member_nif)
    from ...core.errors import CadrumoError
    from ..user_profile.profile_record_repository import ProfileRecordRepository
    from ..user_profile.projections import record_to_values

    try:
        record = ProfileRecordRepository.for_current_session(filing.bucket_id).load(filing.bucket_id)
    except (CadrumoError, OSError) as exc:
        raise LiveApplicationInputError(
            translated_message="application.live.justificante.errors.filing_identity_unresolved",
            context={"filing_record_id": filing.filing_record_id, "profile_record_readable": False},
            precondition_verdict=live_read_no_recovery_verdict(
                LiveReadPrecondition.JUSTIFICANTE_FILING_IDENTITY_RESOLVED,
                facts={
                    "filing_record_id": filing.filing_record_id,
                    "profile_record_readable": False,
                    "tax_id_resolved": False,
                },
            ),
        ) from exc
    values = record_to_values(record)
    tax_id = tax_id_identity_token(str(values.get("identity.tax_id") or values.get("tax.id") or ""))
    if not tax_id:
        raise LiveApplicationInputError(
            translated_message="application.live.justificante.errors.filing_identity_unresolved",
            context={"filing_record_id": filing.filing_record_id, "profile_record_readable": True},
            precondition_verdict=live_read_no_recovery_verdict(
                LiveReadPrecondition.JUSTIFICANTE_FILING_IDENTITY_RESOLVED,
                facts={
                    "filing_record_id": filing.filing_record_id,
                    "profile_record_readable": True,
                    "tax_id_resolved": False,
                },
            ),
        )
    return tax_id


def _justificante_matches_filing_record(
    justificante: Justificante,
    filing: ModeloRecord,
    *,
    expected_tax_id: str,
) -> bool:
    return justificante.matches_filing_target(
        modelo=str(filing.modelo),
        filing_year=filing.filing_year,
        period=filing.period,
        tax_id=expected_tax_id,
    )


expected_tax_id_for_filing_record = _expected_tax_id_for_filing_record
justificante_matches_filing_record = _justificante_matches_filing_record


def _existing_capture_evidence_matches_current_csv(filing: ModeloRecord, csv: str) -> bool:
    evidence = filing.external_evidence
    if evidence is None:
        return False
    kind = getattr(evidence.kind, "value", evidence.kind)
    if str(kind) not in {"aeat_csv_register", "aeat_justificante_pdf", "aeat_live_capture"}:
        return False
    return normalise_aeat_csv(evidence.reference_id) == normalise_aeat_csv(csv)


def stamp_capture_evidence_if_filed(snapshot: JustificanteCaptureSnapshot) -> ModeloRecord | None:
    """Best-effort variant of :func:`register_capture_as_filing_evidence`.

    Returns the stamped :class:`ModeloRecord` when the captured period has a
    current filing record, or ``None`` when none exists yet (the snapshot is
    still persisted; the operator can stamp later by filing the period, then
    re-capturing) or the captured PDF is not parseable into a justificante. Used
    by the capture orchestrator so a capture of a period not yet filed in-app
    does not fail. A present-but-conflicting local filing record is not
    best-effort: identity, period, modelo, and existing-evidence conflicts
    propagate to the caller.
    """
    from ...adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
    from ...domain.justificante import JustificanteParseError

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
