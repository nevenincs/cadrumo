"""Filing-record store paired with filed calculation revisions.

A :class:`ModeloRecord` is the durable receipt of an
internal filing event: at time T, actor A marked calculation revision R of work
unit W as the current filed answer for (bucket, modelo, year, period). The
filing record holds filing-event state (filed timestamp, actor, notes,
origin, AEAT confirmation state, declaration kind, supersession and amendment
links); the filed calculation revision holds
the immutable calculation result. The two are paired so the calculation revision
never accretes filing-side concerns.

There is at most one *current* filing record per (bucket_id, modelo,
filing_year, period) tuple. When a later verified revision is filed,
the previous current record is superseded — its
``superseded_by_filing_record_id`` is set, the calculation revision
it pointed at moves from ``FILED`` to ``FILED_SUPERSEDED``, and the
new filing record becomes current. Both records remain in the
catalogue for audit.

The records of one tuple form a linear chain. A local filing is only an
intention (``PENDIENTE``) until an AEAT register entry proves it was presented
(``CONFIRMADA``); only confirmed records carry :class:`ExternalEvidence`, and
the filing record itself never initiates a live submission.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterator, Mapping
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Self, cast, override

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.filing_year import FilingYear
from ...core.hashing import content_hash_hex
from ...core.identity.aeat_csv import AeatCsv
from ...core.identity.aeat_presentation import AeatPresentationId
from ...core.identity.bucket import BucketId
from ...core.identity.hex_ids import CalculationRevisionId, FilingRecordId, WorkUnitId
from ...core.identity.transaction_ids import TransactionId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...core.time.utc import UtcInstant
from ..filing_evidence import FilingEvidenceReference
from .codes import ModeloCode
from .errors import ModeloValidationError
from .filing_text import EvidenceReference, FilingNotes, ModeloActorLabel

"""Validated string identifying the operator who filed or triggered a filing event.

Strips surrounding whitespace; must be 1–64 characters after stripping.
Used as ``filed_by`` on :class:`ModeloRecord` and feeds into the
content-addressed :func:`derive_filing_record_id`.
"""
_MemberNif = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=32),
]


class ModeloRecordStatus(StrEnum):
    """Closed enumeration of filing-record lifecycle states.

    * ``VIGENTE`` — the record is the currently-effective filed answer
      for its (bucket, modelo, year, period) tuple.
    * ``SUPERSEDIDO`` — a later filing replaced this one. The record
      remains for audit; ``superseded_by_filing_record_id`` points
      at the successor.
    """

    VIGENTE = "vigente"
    SUPERSEDIDO = "supersedido"


class ExternalEvidenceKind(StrEnum):
    """Closed catalogue of external-evidence kinds.

    A :class:`ModeloRecord` marked with one of these kinds
    carries imported official evidence (justificante, CSV register, or live
    capture) rather than a tool-computed calculation revision. This is the gate
    :func:`~cadrumo.application.modelo.amendment_actions.amend_modelo_revision` requires before it
    accepts an amendment baseline.
    """

    AEAT_JUSTIFICANTE_PDF = "aeat_justificante_pdf"
    AEAT_CSV_REGISTER = "aeat_csv_register"
    AEAT_LIVE_CAPTURE = "aeat_live_capture"


def is_justificante_backed_external_evidence(kind: ExternalEvidenceKind) -> bool:
    """Return whether ``kind`` requires matching persisted receipt metadata.

    Every current external-evidence kind is filing-grade only after its
    reference resolves to a matching :class:`domain.justificante.schema.Justificante`.
    Keeping this closed policy beside the enum prevents application consumers
    from silently disagreeing when a new evidence kind is introduced.
    """
    return kind in frozenset(
        {
            ExternalEvidenceKind.AEAT_CSV_REGISTER,
            ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            ExternalEvidenceKind.AEAT_LIVE_CAPTURE,
        },
    )


def is_receipt_bound_external_evidence(kind: ExternalEvidenceKind) -> bool:
    """Return whether ``kind`` requires persisted Justificante metadata."""
    return kind in frozenset(
        {
            ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            ExternalEvidenceKind.AEAT_LIVE_CAPTURE,
        },
    )


class ExternalEvidence(BaseModel):
    """Imported-evidence metadata for an externally-filed return.

    Populated by
    :func:`~cadrumo.application.modelo.external_import_actions.import_external_filing_evidence` for a
    current :class:`ModeloRecord`; consumed by
    :func:`~cadrumo.application.modelo.amendment_actions.amend_modelo_revision` as the gate that
    proves the baseline is AEAT-attested and not a fabricated local draft.
    """

    model_config = STRICT_FROZEN_CONFIG

    kind: ExternalEvidenceKind
    reference_id: EvidenceReference
    imported_at: UtcInstant


class FilingOrigin(StrEnum):
    """Who authored a chain entry: this application, or AEAT's own register."""

    LOCAL = "local"
    AEAT = "aeat"


class AeatConfirmationState(StrEnum):
    """Whether AEAT has been seen to hold a chain entry.

    * ``PENDIENTE`` -- filed locally, not yet observed at AEAT.
    * ``CONFIRMADA`` -- backed by an AEAT register entry and its evidence.
    * ``DISCREPANTE`` -- AEAT holds different content for the presentation; the
      entry is superseded by the AEAT entry.
    * ``DESCARTADA`` -- a pending entry replaced before it was ever presented.
    """

    PENDIENTE = "pendiente"
    CONFIRMADA = "confirmada"
    DISCREPANTE = "discrepante"
    DESCARTADA = "descartada"


_RETIRED_CONFIRMATION_STATES = frozenset({AeatConfirmationState.DISCREPANTE, AeatConfirmationState.DESCARTADA})


class FilingDeclarationKind(StrEnum):
    """Legal kind of a declaration in a period's chain."""

    ORIGINAL = "original"
    COMPLEMENTARIA = "complementaria"
    SUSTITUTIVA = "sustitutiva"
    RECTIFICATIVA = "rectificativa"


class IvaSettlementPaymentState(StrEnum):
    """Evidence state of the declared positive Modelo 303 liability."""

    NOT_APPLICABLE = "not_applicable"
    AWAITING_EVIDENCE = "awaiting_evidence"
    PARTIALLY_EVIDENCED = "partially_evidenced"
    EVIDENCED = "evidenced"


class IvaSettlementRefundState(StrEnum):
    """Independent refund-request, approval, and payment evidence state."""

    NOT_REQUESTED = "not_requested"
    REQUESTED = "requested"
    APPROVED = "approved"
    PAID = "paid"


class IvaCreditSnapshot(BaseModel):
    """Audit copy of the credit disposition for one filed Modelo 303.

    This value validates the filing-time equation but never supplies the active
    carry-forward balance; IVA compensation history remains that owner.
    """

    model_config = STRICT_FROZEN_CONFIG

    opening_amount: Decimal = Field(ge=Decimal("0"))
    generated_amount: Decimal = Field(ge=Decimal("0"))
    applied_amount: Decimal = Field(ge=Decimal("0"))
    remaining_amount: Decimal = Field(ge=Decimal("0"))

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_balanced_credit(self) -> IvaCreditSnapshot:
        available = self.opening_amount + self.generated_amount
        if self.applied_amount > available:
            raise ModeloValidationError("credit snapshot applied_amount exceeds opening plus generated credit")
        if self.remaining_amount != available - self.applied_amount:
            raise ModeloValidationError(
                "credit snapshot remaining_amount must equal opening plus generated minus applied"
            )
        return self


class IvaSettlementPaymentEvidence(BaseModel):
    """One immutable, securely referenced payment fact for a filed Modelo 303."""

    model_config = STRICT_FROZEN_CONFIG

    reference: FilingEvidenceReference
    amount: Decimal = Field(gt=Decimal("0"))
    effective_at: UtcInstant

    @field_validator("amount", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _restore_persisted_amount(cls, value: object) -> object:
        """Restore Decimal values from the encrypted JSON envelope."""
        return Decimal(value) if isinstance(value, str) else value

    @field_validator("effective_at", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _restore_persisted_effective_at(cls, value: object) -> object:
        """Restore UTC instants from the encrypted JSON envelope."""
        return datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value


class IvaSettlementSnapshot(BaseModel):
    """Immutable settlement evidence attached to one filed Modelo 303 revision.

    It records declaration and evidence facts without inferring AEAT acceptance,
    payment, refund approval, or refund payment. Evidence references name
    material already held through the secure filing-evidence custody boundary;
    raw evidence bytes never enter this value.
    """

    model_config = STRICT_FROZEN_CONFIG

    calculation_revision_id: CalculationRevisionId
    declared_liability: Decimal = Field(ge=Decimal("0"))
    payment_evidence: tuple[IvaSettlementPaymentEvidence, ...] = ()
    refund_election_intent: bool = False
    refund_state: IvaSettlementRefundState
    refund_requested_amount: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    refund_approved_amount: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    refund_paid_amount: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    refund_approval_evidence_reference: FilingEvidenceReference | None = None
    refund_approval_effective_at: UtcInstant | None = None
    refund_payment_evidence_reference: FilingEvidenceReference | None = None
    refund_payment_effective_at: UtcInstant | None = None
    credit_snapshot: IvaCreditSnapshot

    @field_validator("payment_evidence", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _collapse_identical_payment_evidence(cls, value: object) -> tuple[IvaSettlementPaymentEvidence, ...]:
        """Keep first-seen evidence order while collapsing only exact duplicates."""
        if value is None:
            return ()
        if not isinstance(value, (list, tuple)):
            raise ModeloValidationError("payment_evidence must be an ordered sequence")
        ordered: list[IvaSettlementPaymentEvidence] = []
        by_reference: dict[str, IvaSettlementPaymentEvidence] = {}
        entries = cast(tuple[object, ...] | list[object], value)
        for raw_entry in entries:
            entry = (
                raw_entry
                if isinstance(raw_entry, IvaSettlementPaymentEvidence)
                else IvaSettlementPaymentEvidence.model_validate(raw_entry)
            )
            reference = entry.reference.reference
            existing = by_reference.get(reference)
            if existing is None:
                by_reference[reference] = entry
                ordered.append(entry)
            elif existing != entry:
                raise ModeloValidationError("payment evidence reference carries conflicting facts")
        return tuple(ordered)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_settlement_evidence_invariants(self) -> IvaSettlementSnapshot:
        _require_evidence_pair(
            reference=self.refund_approval_evidence_reference,
            effective_at=self.refund_approval_effective_at,
            label="refund approval evidence",
        )
        _require_evidence_pair(
            reference=self.refund_payment_evidence_reference,
            effective_at=self.refund_payment_effective_at,
            label="refund payment evidence",
        )
        _require_payment_evidence_total(self)
        _require_refund_state(self)
        return self

    @property
    def evidenced_payment_amount(self) -> Decimal:
        """Return the total recorded by the append-only payment evidence tuple."""
        return sum((entry.amount for entry in self.payment_evidence), Decimal("0"))

    @property
    def payment_state(self) -> IvaSettlementPaymentState:
        """Derive payment state; callers cannot independently assert it."""
        if self.declared_liability == Decimal("0"):
            return IvaSettlementPaymentState.NOT_APPLICABLE
        if self.evidenced_payment_amount == Decimal("0"):
            return IvaSettlementPaymentState.AWAITING_EVIDENCE
        if self.evidenced_payment_amount < self.declared_liability:
            return IvaSettlementPaymentState.PARTIALLY_EVIDENCED
        return IvaSettlementPaymentState.EVIDENCED


def _require_evidence_pair(
    *, reference: FilingEvidenceReference | None, effective_at: UtcInstant | None, label: str
) -> None:
    """Require a secure evidence locator and its effective date together."""
    if (reference is None) != (effective_at is None):
        raise ModeloValidationError(f"{label} requires both an evidence reference and an effective date")


def _require_payment_evidence_total(snapshot: IvaSettlementSnapshot) -> None:
    """Refuse payment evidence that exceeds the declared liability."""
    if snapshot.evidenced_payment_amount > snapshot.declared_liability:
        raise ModeloValidationError("evidenced payment amount must not exceed declared liability")


def _require_refund_state(snapshot: IvaSettlementSnapshot) -> None:
    """Require independent approval and payment evidence for a refund lifecycle."""
    requested = snapshot.refund_requested_amount
    approved = snapshot.refund_approved_amount
    paid = snapshot.refund_paid_amount
    approval_evidenced = snapshot.refund_approval_evidence_reference is not None
    payment_evidenced = snapshot.refund_payment_evidence_reference is not None
    if approved > requested or paid > approved:
        raise ModeloValidationError("refund amounts must satisfy paid <= approved <= requested")
    if snapshot.refund_state is IvaSettlementRefundState.NOT_REQUESTED:
        if (
            requested != Decimal("0")
            or approved != Decimal("0")
            or paid != Decimal("0")
            or approval_evidenced
            or payment_evidenced
        ):
            raise ModeloValidationError("not_requested refund must not carry amounts or evidence")
        return
    if requested <= Decimal("0"):
        raise ModeloValidationError(f"{snapshot.refund_state.value} refund requires a positive requested amount")
    if snapshot.refund_state is IvaSettlementRefundState.REQUESTED:
        if approved != Decimal("0") or paid != Decimal("0") or approval_evidenced or payment_evidenced:
            raise ModeloValidationError("requested refund must not carry approval or payment evidence")
        return
    if approved <= Decimal("0") or not approval_evidenced:
        raise ModeloValidationError("approved refund requires positive approved amount and approval evidence")
    if snapshot.refund_state is IvaSettlementRefundState.APPROVED:
        if paid != Decimal("0") or payment_evidenced:
            raise ModeloValidationError("approved refund must not carry payment evidence")
        return
    if paid <= Decimal("0") or not payment_evidenced:
        raise ModeloValidationError("paid refund requires positive paid amount and payment evidence")


_DECLARATION_KIND_BY_TIPO_SOLICITUD_WORD: Mapping[str, FilingDeclarationKind] = {
    "complementaria": FilingDeclarationKind.COMPLEMENTARIA,
    "sustitutiva": FilingDeclarationKind.SUSTITUTIVA,
    "rectificativa": FilingDeclarationKind.RECTIFICATIVA,
}


def declaration_kind_for_tipo_solicitud(tipo_solicitud: str | None) -> FilingDeclarationKind | None:
    """Return the correction kind an AEAT register ``tipo_solicitud`` names, or ``None``.

    Only a value naming exactly one correction kind is read; any other value,
    including one describing an original declaration, stays ``None`` so the
    caller never assumes a kind AEAT did not state.
    """
    if tipo_solicitud is None:
        return None
    folded = unicodedata.normalize("NFKD", tipo_solicitud).encode("ascii", "ignore").decode("ascii").casefold()
    words = set(re.findall(r"[a-z]+", folded))
    kinds = {kind for word, kind in _DECLARATION_KIND_BY_TIPO_SOLICITUD_WORD.items() if word in words}
    return kinds.pop() if len(kinds) == 1 else None


_TipoSolicitud = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]


class AeatRegisterRef(BaseModel):
    """AEAT's own identifiers for one presented declaration.

    The register expediente and the receipt identifiers (CSV and número de
    justificante) are different AEAT namespaces; each is ``None`` when the
    source did not state it, and at least the expediente or the CSV is present.
    ``presented_at`` is optional because a printed justificante states a
    Europe/Madrid wall-clock time without an offset, and no instant may be
    invented from it.
    """

    model_config = STRICT_FROZEN_CONFIG

    expediente_id: EvidenceReference | None = None
    csv: AeatCsv | None = None
    justificante_number: AeatPresentationId | None = None
    tipo_solicitud: _TipoSolicitud | None = None
    presented_at: UtcInstant | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_an_identifier(self) -> AeatRegisterRef:
        if self.expediente_id is None and self.csv is None:
            raise ModeloValidationError("an AEAT register reference needs an expediente id or a CSV")
        return self


def derive_filing_record_id(
    *,
    work_unit_id: str,
    calculation_revision_id: CalculationRevisionId,
    filed_by: str,
    member_nif: str | None = None,
) -> str:
    """Deterministic 64-char SHA-256 id for a filing record.

    Content-addressed by the filing *outcome* - the parent work unit, the
    filed calculation revision, the actor, and (for member-scoped group
    filings) the member NIF. ``filed_at`` is deliberately excluded from the
    identity so a re-file of the same revision by the same actor resolves to
    the same record (an idempotent re-file is a no-op, not a new time-stamped
    duplicate); ``filed_at`` is retained on :class:`ModeloRecord` as a
    non-identity last-seen field. Member-scoped group filings include the
    member NIF in the identity; single-filer records omit it.
    """
    payload = {
        "work_unit_id": work_unit_id.strip(),
        "calculation_revision_id": calculation_revision_id.strip(),
        "filed_by": filed_by.strip(),
    }
    if member_nif is not None:
        payload["member_nif"] = member_nif.strip()
    return content_hash_hex(payload)


class ModeloRecord(BaseModel):
    """Durable receipt of one internal filing event for an AEAT modelo (tax form).

    Pairs a filed :obj:`CalculationRevisionId` with the
    filing event metadata (actor, timestamp, notes, origin, confirmation state,
    declaration kind, supersession and amendment links). The id is content-addressed by the filing outcome -
    ``work_unit_id``, ``calculation_revision_id``, ``filed_by``, and (for
    member-scoped group filings) ``member_nif`` - via
    :func:`derive_filing_record_id`; ``filed_at`` is a non-identity last-seen
    field, so a re-file of the same revision by the same actor is an
    idempotent no-op rather than a new record. A ``model_validator`` enforces
    the derivation on construction.

    ``confirmation`` records externally-observed AEAT acceptance; it does not
    imply that the application submitted anything. ``CONFIRMADA`` travels with
    :class:`ExternalEvidence` and no other state carries it. An ``AEAT``-origin
    record is always ``CONFIRMADA``; the retired states (``DISCREPANTE``,
    ``DESCARTADA``) are local entries that are no longer in force.
    """

    model_config = STRICT_FROZEN_CONFIG

    filing_record_id: FilingRecordId
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    bucket_id: BucketId
    modelo: ModeloCode
    filing_year: FilingYear
    period: Period
    member_nif: _MemberNif | None = None
    filed_at: UtcInstant
    filed_by: ModeloActorLabel
    notes: FilingNotes | None = None
    origin: FilingOrigin
    confirmation: AeatConfirmationState
    declaration_kind: FilingDeclarationKind
    aeat_register: AeatRegisterRef | None = None
    status: ModeloRecordStatus = ModeloRecordStatus.VIGENTE
    superseded_at: UtcInstant | None = None
    superseded_by_filing_record_id: FilingRecordId | None = None
    external_evidence: ExternalEvidence | None = None
    amends_filing_record_id: FilingRecordId | None = None
    settlement: IvaSettlementSnapshot | None = None
    # Denormalised footprint of the filed revision's contributing ledger
    # transactions, so an external audit tool holding only a filing record
    # resolves its transaction set in one hop. Typed through the canonical
    # :obj:`TransactionId` so the footprint carries real ledger identities the
    # audit tool can look up, not arbitrary strings. Deliberately EXCLUDED from
    # ``derive_filing_record_id`` (mirroring the ledger_filing_snapshot exclusion
    # on the revision hash) so the content address is unaffected; defaults to ()
    # for non-ledger filings.
    source_transaction_ids: tuple[TransactionId, ...] = ()

    @field_validator("source_transaction_ids")
    @classmethod
    @pydantic_validation_boundary
    def _reject_duplicate_source_transactions(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Refuse a repeated transaction in the provenance footprint.

        The footprint is the *set* of ledger rows that contributed to the filed
        revision. A repeat is not a second contribution -- it is either a
        double-counted row or a merge of two footprints -- and silently keeping
        it would make an audit tool reading the record disagree with the ledger
        about how many rows fed the filing.
        """
        duplicates = sorted({entry for entry in value if value.count(entry) > 1})
        if duplicates:
            raise ModeloValidationError(
                f"source_transaction_ids must not repeat a transaction: {duplicates!r}",
            )
        return value

    @field_validator("modelo", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _coerce_modelo(cls, value: object) -> ModeloCode:
        if isinstance(value, ModeloCode):
            return value
        if isinstance(value, str):
            return ModeloCode(value)
        raise ModeloValidationError(f"expected ModeloCode or str, got {type(value).__name__}")

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _enforce_invariants(self) -> ModeloRecord:
        _require_filing_record_identity(self)
        _require_external_evidence_state(self)
        _require_filing_record_status(self)
        _require_settlement_modelo(self)
        return self

    @property
    def aeat_accepted(self) -> bool:
        """Return whether AEAT has been observed to hold this entry."""
        return self.confirmation is AeatConfirmationState.CONFIRMADA

    @property
    def is_retired(self) -> bool:
        """Return whether the entry left the chain without being the presented declaration."""
        return self.confirmation in _RETIRED_CONFIRMATION_STATES

    @override
    def model_copy(self, *, update: Mapping[str, object] | None = None, deep: bool = False) -> Self:
        copied = super().model_copy(update=update, deep=deep)
        if update:
            return type(self).model_validate(copied.model_dump(mode="python"))
        return copied


def _require_filing_record_identity(record: ModeloRecord) -> None:
    """Require the filing record's period and content-addressed identity to agree."""
    if record.period.filing_year != record.filing_year:
        raise ModeloValidationError(
            f"filing_year {record.filing_year!r} does not match period year {record.period.filing_year!r}",
        )
    derived = derive_filing_record_id(
        work_unit_id=record.work_unit_id,
        calculation_revision_id=record.calculation_revision_id,
        filed_by=record.filed_by,
        member_nif=record.member_nif,
    )
    if derived != record.filing_record_id:
        raise ModeloValidationError(
            f"filing_record_id {record.filing_record_id!r} does not match the derived id {derived!r}",
        )


def _require_external_evidence_state(record: ModeloRecord) -> None:
    """Require origin, confirmation, evidence and register reference to agree."""
    confirmed = record.confirmation is AeatConfirmationState.CONFIRMADA
    if record.origin is FilingOrigin.AEAT and not confirmed:
        raise ModeloValidationError("AEAT-origin filing record must be confirmed")
    if confirmed and record.external_evidence is None:
        raise ModeloValidationError("confirmed filing record must carry external evidence")
    if record.external_evidence is not None and not confirmed:
        raise ModeloValidationError(
            f"{record.confirmation.value} filing record must not carry external evidence",
        )
    if record.aeat_register is not None and not confirmed:
        raise ModeloValidationError(
            f"{record.confirmation.value} filing record must not carry an AEAT register reference",
        )
    if record.is_retired and record.status is ModeloRecordStatus.VIGENTE:
        raise ModeloValidationError(f"{record.confirmation.value} filing record cannot be in force")


def _require_filing_record_status(record: ModeloRecord) -> None:
    """Require lifecycle metadata to match the record's current or superseded state."""
    if record.status is ModeloRecordStatus.VIGENTE:
        _require_current_filing_record(record)
    else:
        _require_superseded_filing_record(record)


def _require_settlement_modelo(record: ModeloRecord) -> None:
    """Keep the optional IVA settlement snapshot on Modelo 303 records only."""
    settlement = record.settlement
    if settlement is None:
        return
    if str(record.modelo) != "303":
        raise ModeloValidationError("an IVA settlement snapshot requires Modelo 303")
    if settlement.calculation_revision_id != record.calculation_revision_id:
        raise ModeloValidationError("IVA settlement calculation revision must match its filing record")
    if (
        record.confirmation is not AeatConfirmationState.CONFIRMADA
        and settlement.refund_state is not IvaSettlementRefundState.NOT_REQUESTED
    ):
        raise ModeloValidationError("pending filing records may carry only not_requested IVA refund intent")


def _require_current_filing_record(record: ModeloRecord) -> None:
    """Reject supersession metadata on the current filing record."""
    if record.superseded_at is not None or record.superseded_by_filing_record_id is not None:
        raise ModeloValidationError("current filing record must not carry supersession metadata")


def _require_superseded_filing_record(record: ModeloRecord) -> None:
    """Require complete, chronologically ordered supersession metadata."""
    if record.superseded_at is None or record.superseded_by_filing_record_id is None:
        raise ModeloValidationError(
            "superseded filing record must carry superseded_at and superseded_by_filing_record_id",
        )
    if record.superseded_at < record.filed_at:
        raise ModeloValidationError(
            f"superseded_at {record.superseded_at.isoformat()} precedes filed_at {record.filed_at.isoformat()}",
        )


class ModeloRecordCatalogue(BaseModel):
    """Immutable catalogue of every filing record in a bucket's storage.

    Keyed by ``filing_record_id``; the model validator enforces that every
    key equals the id of the :class:`ModeloRecord` it maps to, and that at
    most one record per (bucket_id, modelo, filing_year, period,
    member_nif) tuple carries ``status=VIGENTE``. Iteration yields
    :class:`ModeloRecord` values (not key–value pairs) — the override is
    annotated with a suppression comment on ``__iter__``.
    """

    model_config = STRICT_FROZEN_CONFIG

    records: Mapping[str, ModeloRecord] = Field(default_factory=dict)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _enforce_keys_match(self) -> ModeloRecordCatalogue:
        for key, record in self.records.items():
            if key != record.filing_record_id:
                raise ModeloValidationError(
                    f"catalogue key {key!r} does not match filing_record_id {record.filing_record_id!r}",
                )
        # Exactly one CURRENT record per (bucket, modelo, year, period, member) tuple.
        currents: dict[tuple[str, str, int, Period, str | None], str] = {}
        for record in self.records.values():
            if record.status is not ModeloRecordStatus.VIGENTE:
                continue
            current_key = (
                record.bucket_id,
                record.modelo,
                record.filing_year,
                record.period,
                record.member_nif,
            )
            if current_key in currents:
                raise ModeloValidationError(
                    f"more than one current filing record for {current_key!r}: "
                    f"{currents[current_key]!r} and {record.filing_record_id!r}",
                )
            currents[current_key] = record.filing_record_id
        return self

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _enforce_amendment_links_resolve(self) -> ModeloRecordCatalogue:
        """Resolve every ``amends_filing_record_id`` to a real, distinct, same-coordinate record.

        A declaración complementaria corrects one earlier filing for the same
        (bucket, modelo, filing_year, period, member_nif) coordinate. The field
        alone is shape-validated, so without this a record could claim to amend
        a filing that does not exist, or itself, and the catalogue would accept
        the claim as a valid audit chain.

        The amendment relationship is stored twice -- forwards as the
        amendment's ``amends_filing_record_id`` and backwards as the baseline's
        ``superseded_by_filing_record_id`` -- so the two records must agree
        about it. A one-sided link, where the baseline names some third record
        as its successor, describes an audit chain that reads differently
        depending on which end you start from. The sibling
        :func:`~domain.invoices.service.verify_link_consistency` *reports* the
        equivalent one-sided state across the invoice and transaction
        catalogues, because those are two independently-written stores that can
        legitimately be inconsistent between writes; both ends of this link live
        in one catalogue written in one call, so here it is a refusal.

        ``member_nif`` is part of the compared coordinate: the amendment
        builder propagates it verbatim from the baseline, so a member-scoped
        amendment that landed on the wrong member (or dropped it to the
        single-filer ``None`` slot) is refused here rather than silently
        colliding with an unrelated current record in
        :meth:`ModeloRecordCatalogue._enforce_keys_match`.

        Retired entries (``DESCARTADA``, ``DISCREPANTE``) keep their forward
        link as history, but the chain has since moved on: the baseline they
        named now points at the entry that replaced them, so their links are
        not checked.

        One deliberate exclusion: the target's ``status`` is not asserted to be
        ``SUPERSEDIDO``. :meth:`ModeloRecord._enforce_invariants` already
        refuses a ``VIGENTE`` record that carries supersession metadata, so a
        target whose ``superseded_by_filing_record_id`` matches is necessarily
        superseded; restating it here would be a second spelling of one rule.
        """
        for record in self.records.values():
            target_id = record.amends_filing_record_id
            if target_id is None or record.is_retired:
                continue
            if target_id == record.filing_record_id:
                raise ModeloValidationError(
                    f"filing record {record.filing_record_id!r} cannot amend itself",
                )
            target = self.records.get(target_id)
            if target is None:
                raise ModeloValidationError(
                    f"filing record {record.filing_record_id!r} amends {target_id!r}, which is not in this catalogue",
                )
            coordinates = (record.bucket_id, record.modelo, record.filing_year, record.period, record.member_nif)
            target_coordinates = (
                target.bucket_id,
                target.modelo,
                target.filing_year,
                target.period,
                target.member_nif,
            )
            if coordinates != target_coordinates:
                raise ModeloValidationError(
                    f"filing record {record.filing_record_id!r} amends {target_id!r} across filing "
                    f"coordinates: {target_coordinates!r} is not {coordinates!r}",
                )
            if target.superseded_by_filing_record_id != record.filing_record_id:
                raise ModeloValidationError(
                    f"one-sided amendment link: filing record {record.filing_record_id!r} amends "
                    f"{target_id!r}, but {target_id!r} names "
                    f"{target.superseded_by_filing_record_id!r} as its successor",
                )
        return self

    def get(self, filing_record_id: str) -> ModeloRecord | None:
        """Return the :class:`ModeloRecord` for ``filing_record_id``, or ``None``."""
        return self.records.get(filing_record_id)

    def current_for(
        self,
        *,
        bucket_id: str,
        modelo: str,
        filing_year: int,
        period: Period,
        member_nif: str | None = None,
    ) -> ModeloRecord | None:
        """Return the current (non-superseded) :class:`ModeloRecord` for a filing tuple.

        Returns ``None`` when no filing has ever happened for the
        tuple. ``member_nif=None`` means the single-filer or aggregate
        record, not every member. Returns the active filing record when
        one exists. Never returns a superseded record — callers must
        iterate :attr:`records` directly to walk audit history.
        """
        expected_member_nif = member_nif.strip() if member_nif is not None else None
        for record in self.records.values():
            if record.status is not ModeloRecordStatus.VIGENTE:
                continue
            if (
                record.bucket_id == bucket_id
                and record.modelo == modelo
                and record.filing_year == filing_year
                and record.period == period
                and record.member_nif == expected_member_nif
            ):
                return record
        return None

    def latest_confirmed_for(
        self,
        *,
        bucket_id: str,
        modelo: str,
        filing_year: int,
        period: Period,
        member_nif: str | None = None,
    ) -> ModeloRecord | None:
        """Return the most recent AEAT-confirmed record for a filing tuple.

        This is the declaration a correction must reference. It differs from
        :meth:`current_for` while a local entry is pending.
        """
        current = self.current_for(
            bucket_id=bucket_id,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            member_nif=member_nif,
        )
        if current is not None and current.aeat_accepted:
            return current
        history = self.history_for(
            bucket_id=bucket_id,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            member_nif=member_nif,
        )
        return next((record for record in reversed(history) if record.aeat_accepted), None)

    def history_for(
        self,
        *,
        bucket_id: str,
        modelo: str,
        filing_year: int,
        period: Period,
        member_nif: str | None = None,
    ) -> tuple[ModeloRecord, ...]:
        """Return every filing record for a tuple, ordered by filed_at.

        Returns:
            Tuple of :class:`ModeloRecord` objects ordered by filing timestamp.
        """
        expected_member_nif = member_nif.strip() if member_nif is not None else None
        matching = tuple(
            record
            for record in self.records.values()
            if record.bucket_id == bucket_id
            and record.modelo == modelo
            and record.filing_year == filing_year
            and record.period == period
            and record.member_nif == expected_member_nif
        )
        return tuple(sorted(matching, key=lambda r: r.filed_at))

    def values(self):
        """Return a view of all :class:`ModeloRecord` values in the catalogue."""
        return self.records.values()

    @override
    def __iter__(self) -> Iterator[ModeloRecord]:  # pyright: ignore[reportIncompatibleMethodOverride]  # ty: ignore[invalid-method-override]  # pyrefly: ignore[bad-override]  # reason: intentional Pydantic catalogue iteration adapter; the established public API yields ModeloRecord records, not BaseModel field-value tuples
        """Iterate over :class:`ModeloRecord` values (not ``(key, value)`` pairs)."""
        return iter(self.records.values())

    def __len__(self) -> int:
        """Return the number of filing records in the catalogue."""
        return len(self.records)

    def __contains__(self, key: object) -> bool:
        """Test membership by :class:`ModeloRecord` instance or ``filing_record_id`` string."""
        if isinstance(key, ModeloRecord):
            return key.filing_record_id in self.records
        if isinstance(key, str):
            return key in self.records
        return False


__all__ = [
    "AeatConfirmationState",
    "AeatRegisterRef",
    "ExternalEvidence",
    "ExternalEvidenceKind",
    "FilingDeclarationKind",
    "FilingOrigin",
    "IvaCreditSnapshot",
    "IvaSettlementPaymentState",
    "IvaSettlementRefundState",
    "IvaSettlementSnapshot",
    "ModeloRecord",
    "ModeloRecordCatalogue",
    "ModeloRecordStatus",
    "declaration_kind_for_tipo_solicitud",
    "derive_filing_record_id",
    "is_justificante_backed_external_evidence",
    "is_receipt_bound_external_evidence",
]
