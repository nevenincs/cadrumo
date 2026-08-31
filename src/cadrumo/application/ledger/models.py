"""Strict Pydantic contracts for manual ledger transaction workflows."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Self

from pydantic import AfterValidator, BaseModel, Field, field_validator, model_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import Art104TresExclusion, Hex64Str, IvaDeductionFactKind, Period

# CLASSIFIED_BY_MANUAL is re-exported for constants centralisation tests.
from ...core.external_constants import (
    CLASSIFIED_BY_MANUAL as CLASSIFIED_BY_MANUAL,
)
from ...core.external_constants import (
    DEFAULT_CURRENCY,
)
from ...core.identity import BucketId, CalculationRevisionId, ContentDigest, TransactionId, WorkUnitId
from ...core.parsing import normalise_iso_3166_alpha2_jurisdiction, normalise_iso_4217_currency
from ...domain.iva import (
    EUMemberState,
    InputClassification,
    IvaCategory,
)
from ...domain.transactions import (
    BucketTransactionRef,
    BusinessClassification,
    ImportSummary,
    M210IncomeClassification,
    Transaction,
    TransactionDirection,
    TransactionEditLineageEntry,
    TransactionEvidenceProvenanceEntry,
    TransactionLifecycleLineageEntry,
    TransactionValidationError,
)
from ..export import ExportSerializationFormat, verify_export_metadata
from ..review.filter import LedgerReviewStatus

_TRANSFER_ALLOWED_STATES = frozenset(
    {
        BusinessClassification.NOT_YET_PROCESSED,
        BusinessClassification.PERSONAL,
        BusinessClassification.PROCESSED_UNCLASSIFIED,
        BusinessClassification.SKIPPED_BY_RULE,
    },
)


def _validate_iso_3166_jurisdiction(value: str | None) -> str | None:
    """Validate and normalise an ISO 3166-1 alpha-2 field value.

    Shared by ``source_jurisdiction`` and ``counterparty_country``, which are
    different FACTS -- where income arises, and where the counterparty is
    established -- that happen to share one shape. They are validated together
    only so a single model cannot accept two spellings of a country code; no
    call site may read either as the other.

    Accepts ``None`` (no jurisdiction declared) or a two-letter
    ISO 3166-1 alpha-2 uppercase country code such as ``"ES"`` or ``"DE"``.
    Strips surrounding whitespace before the check; raises :class:`ValueError`
    if the result is not exactly two ASCII alphabetic uppercase characters.

    Used by :class:`ManualLedgerTransactionCommand`,
    :class:`ManualLedgerTransactionPatch`, :class:`LedgerTransactionPayload`,
    and :class:`LedgerTransactionReviewPayload` as a shared ``@field_validator``
    body, replacing four identical inline copies.

    The shape policy itself is owned by
    :func:`~core.parsing.normalise_iso_3166_alpha2_jurisdiction`, shared with
    :meth:`domain.transactions.Transaction._validate_source_jurisdiction`, so
    the application and domain boundaries cannot drift apart on which
    jurisdiction tokens they accept. This wrapper exists only to keep the
    application-layer :class:`ValueError` boundary.
    """
    return normalise_iso_3166_alpha2_jurisdiction(value)


def _normalise_optional_ledger_text(value: str | None) -> str | None:
    """Strip an optional ledger input, collapsing blanks to an absent value."""
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


_LedgerOptionalText = Annotated[str | None, AfterValidator(_normalise_optional_ledger_text)]


class _LedgerCountryCodeModel(BaseModel):
    """Canonical ISO-country normalization for ledger command and read models."""

    model_config = _STRICT_FROZEN

    @field_validator("source_jurisdiction", "counterparty_country", check_fields=False)
    @classmethod
    def _normalise_country_codes(cls, value: str | None) -> str | None:
        return _validate_iso_3166_jurisdiction(value)


class _ManualLedgerTransactionInput(_LedgerCountryCodeModel):
    """Canonical input normalization shared by manual-ledger create and patch DTOs."""

    @field_validator("currency", mode="before", check_fields=False)
    @classmethod
    def _normalise_currency(cls, value: object) -> object:
        if value is None:
            return None
        return normalise_iso_4217_currency(value)

    @field_validator("attachment_ids", check_fields=False)
    @classmethod
    def _normalise_identifier_tuple(cls, value: tuple[str, ...] | None) -> tuple[str, ...] | None:
        if value is None:
            return None
        normalised = tuple(item.strip() for item in value if item.strip())
        if len(set(normalised)) != len(normalised):
            raise ValueError("identifier tuple must not contain duplicates")
        return normalised


class ManualLedgerTransactionCommand(_ManualLedgerTransactionInput):
    """Backend command for creating or updating one manual ledger transaction."""

    bucket_id: BucketId
    booked_date: date
    value_date: date | None = None
    amount: Decimal
    currency: str = Field(default=DEFAULT_CURRENCY, min_length=3)
    direction: TransactionDirection
    counterparty: _LedgerOptionalText = None
    description: str = Field(min_length=1)
    business_classification: BusinessClassification = BusinessClassification.NOT_YET_PROCESSED
    business_pct: Decimal | None = None
    category_id: _LedgerOptionalText = None
    taxable_base: Decimal | None = None
    iva_rate: Decimal | None = None
    iva_amount: Decimal | None = None
    recargo_amount: Decimal | None = None
    irpf_category: _LedgerOptionalText = None
    m210_income_classification: M210IncomeClassification | None = None
    usage_ratio_id: _LedgerOptionalText = None
    prorrata_reference: _LedgerOptionalText = None
    purchase_invoice_evidence_id: _LedgerOptionalText = None
    attachment_ids: tuple[str, ...] = ()
    notes: str = ""
    iva_category: IvaCategory | None = None
    #: Operator-declared M303 deduction source. The taxonomy is documented as
    #: non-inferable, so it is carried from the operator rather than derived
    #: from the category, the direction, or the counterparty country.
    deduction_fact_kind: IvaDeductionFactKind | None = None
    counterparty_country: str | None = None
    counterparty_identification_state: EUMemberState | None = None
    art_104_tres_exclusion: Art104TresExclusion | None = None
    input_classification: InputClassification | None = None
    prorrata_sector_id: str | None = Field(default=None, min_length=1, max_length=64)
    actor: str = Field(default="operator", min_length=1)
    source_command: str = Field(default="aeat app ledger add", min_length=1)
    idempotency_key: _LedgerOptionalText = None
    classified_by_override: _LedgerOptionalText = None
    source_jurisdiction: str | None = None
    group_label: str | None = Field(default=None, max_length=64)

    @field_validator(
        "bucket_id",
        "description",
        "actor",
        "source_command",
    )
    @classmethod
    def _trim_required_text(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("field must not be blank")
        return trimmed

    @field_validator("notes")
    @classmethod
    def _trim_notes(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def _validate_business_percentage(self) -> Self:
        if self.business_classification is BusinessClassification.MIXED:
            if self.business_pct is None:
                raise TransactionValidationError("business_pct is required when classification is MIXED")
            if not Decimal("0") <= self.business_pct <= Decimal("1"):
                raise TransactionValidationError("business_pct must be within 0..1 when classification is MIXED")
            return self
        if self.business_pct is not None:
            raise TransactionValidationError("business_pct must be None unless classification is MIXED")
        return self

    @model_validator(mode="after")
    def _validate_direction_policy(self) -> Self:
        if self.amount < Decimal("0"):
            raise TransactionValidationError(
                "manual ledger transaction amount must be a non-negative magnitude; "
                "set the flow with --direction (OUTGOING / INCOMING / INTERNAL_TRANSFER), not a negative amount",
            )
        if self.amount == Decimal("0"):
            raise TransactionValidationError(
                "manual ledger transaction amount must be non-zero; attach zero-value evidence to an existing row",
            )
        if self.direction is TransactionDirection.INTERNAL_TRANSFER:
            self._validate_internal_transfer_payload()
        return self

    def _validate_internal_transfer_payload(self) -> None:
        if self.business_classification not in _TRANSFER_ALLOWED_STATES:
            raise TransactionValidationError(
                "INTERNAL_TRANSFER rows must not be classified as tax-relevant business rows",
            )
        forbidden = {
            "category_id": self.category_id,
            "taxable_base": self.taxable_base,
            "iva_rate": self.iva_rate,
            "iva_amount": self.iva_amount,
            "recargo_amount": self.recargo_amount,
            "irpf_category": self.irpf_category,
            "m210_income_classification": self.m210_income_classification,
            "usage_ratio_id": self.usage_ratio_id,
            "prorrata_reference": self.prorrata_reference,
            "art_104_tres_exclusion": self.art_104_tres_exclusion,
            "input_classification": self.input_classification,
            "prorrata_sector_id": self.prorrata_sector_id,
            "purchase_invoice_evidence_id": self.purchase_invoice_evidence_id,
            "attachment_ids": self.attachment_ids,
        }
        populated = tuple(key for key, value in forbidden.items() if value not in (None, ()))
        if populated:
            joined = ", ".join(populated)
            raise TransactionValidationError(f"INTERNAL_TRANSFER rows must not carry tax or evidence fields: {joined}")


class ManualLedgerTransactionPatch(_ManualLedgerTransactionInput):
    """Typed partial update for one bucket-scoped ledger transaction."""

    booked_date: date | None = None
    value_date: date | None = None
    amount: Decimal | None = None
    currency: str | None = None
    direction: TransactionDirection | None = None
    counterparty: _LedgerOptionalText = None
    description: _LedgerOptionalText = None
    business_classification: BusinessClassification | None = None
    business_pct: Decimal | None = None
    category_id: _LedgerOptionalText = None
    taxable_base: Decimal | None = None
    iva_rate: Decimal | None = None
    iva_amount: Decimal | None = None
    recargo_amount: Decimal | None = None
    irpf_category: _LedgerOptionalText = None
    m210_income_classification: M210IncomeClassification | None = None
    usage_ratio_id: _LedgerOptionalText = None
    prorrata_reference: _LedgerOptionalText = None
    purchase_invoice_evidence_id: _LedgerOptionalText = None
    attachment_ids: tuple[str, ...] | None = None
    notes: _LedgerOptionalText = None
    iva_category: IvaCategory | None = None
    deduction_fact_kind: IvaDeductionFactKind | None = None
    counterparty_country: str | None = None
    counterparty_identification_state: EUMemberState | None = None
    source_jurisdiction: str | None = None
    group_label: _LedgerOptionalText = None

    @model_validator(mode="after")
    def _require_change(self) -> Self:
        if not self.model_fields_set:
            raise TransactionValidationError("manual ledger patch must carry at least one field")
        return self


class ManualLedgerTransactionResult(BaseModel):
    """Backend result for a persisted manual ledger transaction mutation.

    ``stale_finalized_revisions`` is populated only by an evidence-only
    attachment that landed on a row a finalized revision cites. Those revisions
    bundled their ledger evidence BEFORE the attachment, so their frozen bundles
    no longer show the proof the row now carries: the operator must recalculate
    for the evidence to reach a draft. The field is structured provenance for the
    caller to project into an operator notice, never a refusal.
    """

    model_config = _STRICT_FROZEN

    ref: BucketTransactionRef
    transaction: Transaction
    bucket_event_ids: tuple[str, ...] = ()
    stale_finalized_revisions: tuple[LedgerRemovalBlocker, ...] = ()


class LedgerTransactionPayload(_LedgerCountryCodeModel):
    """Canonical read projection for one ledger transaction."""

    transaction_id: TransactionId
    date: str = Field(min_length=10, max_length=10)
    booked_date: str = Field(min_length=10, max_length=10)
    value_date: str | None = None
    amount: str = Field(min_length=1)
    currency: str = Field(min_length=3, max_length=3)
    direction: str = Field(min_length=1)
    counterparty: str = ""
    description: str = Field(min_length=1)
    business_classification: str = Field(min_length=1)
    business_pct: str | None = None
    category_id: str | None = None
    taxable_base: str | None = None
    iva_rate: str | None = None
    iva_amount: str | None = None
    iva_category: str | None = None
    counterparty_country: str | None = None
    counterparty_identification_state: str | None = None
    irpf_category: str | None = None
    m210_income_classification: M210IncomeClassification | None = None
    usage_ratio_id: str | None = None
    prorrata_reference: str | None = None
    purchase_invoice_evidence_id: str | None = None
    attachment_ids: tuple[str, ...] = ()
    notes: str = ""
    lifecycle_state: str = Field(min_length=1)
    classified_by: str = Field(min_length=1)
    # Decision-provenance fields: the "why" behind the active
    # classification decision, surfaced alongside `classified_by` so an
    # operator can answer "why was this classified as X" from one read.
    classified_at: str | None = None
    classification_reason: str = ""
    classification_confidence: str | None = None
    source_jurisdiction: str | None = None
    # FX provenance for foreign-currency rows: the
    # EUR-equivalent and the applied CCY->EUR rate, so list/review/export surface
    # the converted value rather than only the native amount. None for EUR rows.
    value_in_eur: str | None = None
    fx_rate: str | None = None
    # Persistence-record lifecycle timestamps (ledger-interface-contract D6),
    # rendered as ISO-8601 strings.
    created_at: str
    modified_at: str


class LedgerTransactionReviewPayload(LedgerTransactionPayload):
    """Canonical read projection for one ledger transaction plus review status.

    Extends :class:`LedgerTransactionPayload` with the derived operator
    ``review_status`` so the two projections share one field set, validator, and
    config; ``review_status`` serialises after the inherited fields.
    """

    review_status: LedgerReviewStatus


class LedgerTransactionResultPayload(BaseModel):
    """Canonical projection for a single ledger mutation/read result."""

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    transaction_id: TransactionId
    review_status: LedgerReviewStatus
    transaction: LedgerTransactionPayload


class LedgerTransactionTrackingPayload(BaseModel):
    """Durable event lineage fields for one ledger transaction."""

    model_config = _STRICT_FROZEN

    transaction_id: TransactionId
    # Imported transactions carry no creation bucket-event id (it is set only
    # for rows created via `ledger add`); `ledger track` must render lineage for
    # imported rows too, so this field is nullable rather than required.
    created_event_id: str | None = Field(default=None, min_length=1)
    evidence_provenance: tuple[TransactionEvidenceProvenanceEntry, ...]
    edit_lineage: tuple[TransactionEditLineageEntry, ...]
    lifecycle_state: str = Field(min_length=1)
    lifecycle_lineage: tuple[TransactionLifecycleLineageEntry, ...]


class SplitChildCommand(BaseModel):
    """One slice of an N-way split.

    Attributes:
        amount: Non-negative magnitude Decimal in the parent's currency;
            direction is inherited from the parent (the split builder copies
            ``parent.direction`` onto every child).
        description: Non-blank narrative for this slice.
        counterparty: Optional override; falls back to the parent's
            counterparty when ``None``.
        booked_date: Optional override; falls back to the parent's
            ``booked_date``.
        value_date: Optional override; falls back to the parent's
            ``value_date``.
    """

    model_config = _STRICT_FROZEN

    amount: Decimal
    description: str = Field(min_length=1, max_length=1024)
    counterparty: str | None = None
    booked_date: date | None = None
    value_date: date | None = None

    @field_validator("description")
    @classmethod
    def _trim_description(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("description must not be blank")
        return trimmed

    @field_validator("counterparty")
    @classmethod
    def _trim_counterparty(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None


class SplitTransactionResult(BaseModel):
    """Backend result of a successful N-way split."""

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    parent_transaction_id: TransactionId
    split_group_id: Hex64Str
    child_transaction_ids: tuple[str, ...]
    parent_transaction: Transaction
    child_transactions: tuple[Transaction, ...]
    bucket_event_id: Hex64Str


class MergeTransactionsResult(BaseModel):
    """Backend result of a successful split re-merge."""

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    split_group_id: Hex64Str
    parent_transaction_id: TransactionId
    merged_transaction_id: TransactionId
    source_child_ids: tuple[str, ...]
    merged_transaction: Transaction
    parent_transaction: Transaction
    bucket_event_id: Hex64Str


class LedgerImportOperationResult(BaseModel):
    """Backend result for an imported ledger transaction batch."""

    model_config = _STRICT_FROZEN

    summary: ImportSummary
    import_batch_id: Hex64Str | None = None
    bucket_event_ids: tuple[str, ...] = ()


class LedgerSourceValidationReport(BaseModel):
    """Backend read model for source-provider validation details."""

    model_config = _STRICT_FROZEN

    valid: bool
    warnings: tuple[str, ...] = ()
    encoding: str | None = None
    dialect: str | None = None


class LedgerSourceVerificationReport(BaseModel):
    """Backend read model for optional source-file verification."""

    model_config = _STRICT_FROZEN

    requested: bool
    path: str | None = None
    sha256: str | None = None


class LedgerImportDiagnosticReport(BaseModel):
    """Backend read model for one persisted or dry-run import diagnostic."""

    model_config = _STRICT_FROZEN

    kind: str = Field(min_length=1, max_length=32)
    severity: str = Field(min_length=1, max_length=16)
    message: str = Field(min_length=1, max_length=128)
    source_path: str | None = None
    source_locator: str | None = None
    affected_transaction_ids: tuple[str, ...] = ()


class LedgerSourceImportCommand(BaseModel):
    """Backend command for importing ledger rows from an operator source file."""

    model_config = _STRICT_FROZEN

    bucket_id: BucketId | None = Field(default=None)
    path: Path
    provider: str = Field(min_length=1)
    dry_run: bool = False
    verify: bool = False
    source: Path | None = None
    period: Period | None = None
    actor: str = Field(default="operator", min_length=1, max_length=64)
    source_command: str = Field(default="aeat app ledger import", min_length=1, max_length=128)

    @field_validator("bucket_id", "provider", "actor", "source_command")
    @classmethod
    def _trim_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            raise TransactionValidationError("ledger source import command text fields must not be blank")
        return trimmed


class LedgerSourceImportResult(BaseModel):
    """Backend result for source-file import diagnostics and persistence."""

    model_config = _STRICT_FROZEN

    rows: int = Field(ge=0)
    imported: int = Field(ge=0)
    skipped: int = Field(ge=0)
    likely_duplicates: int = Field(default=0, ge=0)
    dry_run: bool
    verify: bool
    period: Period | None = None
    bucket_id: BucketId | None = None
    import_batch_id: str | None = None
    bucket_event_ids: tuple[str, ...] = ()
    imported_transaction_refs: tuple[BucketTransactionRef, ...] = ()
    skipped_transaction_refs: tuple[BucketTransactionRef, ...] = ()
    likely_duplicate_transaction_refs: tuple[BucketTransactionRef, ...] = ()
    validation: LedgerSourceValidationReport
    source: LedgerSourceVerificationReport
    diagnostics: tuple[LedgerImportDiagnosticReport, ...] = ()


class LedgerReviewQuery(BaseModel):
    """Backend query for operator review rows in one bucket ledger."""

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    period: Period | None = None
    status: str | None = None
    issue: str | None = None
    import_id: str | None = None
    classification: str | None = None
    text: str | None = None
    direction: str | None = None
    transaction_id: TransactionId | None = None

    @field_validator(
        "bucket_id",
        "status",
        "issue",
        "import_id",
        "classification",
        "text",
        "direction",
        "transaction_id",
    )
    @classmethod
    def _trim_optional_query_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            raise TransactionValidationError("ledger review query text fields must not be blank")
        return trimmed


class LedgerReviewRow(BaseModel):
    """Backend projection for one ledger review row.

    ``id`` is the content-addressed ledger transaction identity, not merely a
    64-character string: it is the value the operator passes back to address
    the row, so an id that is the right length but not a digest names nothing.
    """

    model_config = _STRICT_FROZEN

    id: TransactionId
    date: str = Field(min_length=10, max_length=10)
    amount: str = Field(min_length=1)
    description: str = Field(min_length=1)
    status: str = Field(min_length=1)
    transaction: LedgerTransactionPayload | None = None


class LedgerReviewQueryResult(BaseModel):
    """Backend result for operator ledger review queries."""

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    rows: tuple[LedgerReviewRow, ...]
    filters: tuple[str, ...] = ()


class LedgerStatusReport(BaseModel):
    """Backend read model summarizing one bucket's ledger transaction state."""

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    # Money roll-up over active business/mixed rows (period-scoped when --period
    # is given): the readiness/year-end money picture (gross EUR, not a registry
    # calculation).
    business_income_total: str = "0.00"
    business_expense_total: str = "0.00"
    business_net_total: str = "0.00"
    total_count: int = Field(ge=0)
    active_count: int = Field(ge=0)
    archived_count: int = Field(ge=0)
    stashed_count: int = Field(ge=0)
    split_count: int = Field(ge=0, default=0)
    pending_review_count: int = Field(ge=0)
    reviewed_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    period: Period | None = None
    checked_transaction_count: int = Field(default=0, ge=0)
    readiness_issue_count: int = Field(default=0, ge=0)
    ready: bool | None = None


class LedgerRemovalBlocker(BaseModel):
    """Finalized modelo revision that prevents ledger transaction removal."""

    model_config = _STRICT_FROZEN

    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    revision_state: str = Field(min_length=1)
    modelo: str = Field(min_length=1, max_length=16)
    filing_year: int = Field(ge=2000, le=2099)
    period: str = Field(min_length=1, max_length=16)


class LedgerTransactionRemovalReport(BaseModel):
    """Backend report for one bucket-local ledger transaction removal."""

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    transaction_id: TransactionId
    removed: bool = False
    dry_run: bool = False
    actor: str = Field(min_length=1, max_length=64)
    reason: str = ""
    cascaded_purchase_invoice_evidence_ids: tuple[str, ...] = ()
    cascaded_attachment_ids: tuple[str, ...] = ()
    blocking_modelo_references: tuple[LedgerRemovalBlocker, ...] = ()
    # DRAFT (BORRADOR) revisions that still cite the removed row. Removal
    # proceeds, but each named draft will assert an income/expense no longer in
    # the books until recalculated; surfaced as a non-blocking advisory, kept
    # distinct from ``blocking_modelo_references`` (no-silent-under-declaration).
    stale_draft_revision_references: tuple[LedgerRemovalBlocker, ...] = ()
    bucket_event_ids: tuple[str, ...] = ()


class LedgerCatalogueResetReport(BaseModel):
    """Backend report for a protected bucket-local ledger catalogue reset."""

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    removed_transaction_ids: tuple[str, ...] = ()
    reset: bool = False
    dry_run: bool = False
    actor: str = Field(min_length=1, max_length=64)
    reason: str = ""
    cascaded_purchase_invoice_evidence_ids: tuple[str, ...] = ()
    cascaded_attachment_ids: tuple[str, ...] = ()
    blocking_modelo_references: tuple[LedgerRemovalBlocker, ...] = ()
    # DRAFT (BORRADOR) revisions that still cite a reset row. Reset proceeds, but
    # each named draft will assert an income/expense no longer in the books until
    # recalculated; surfaced as a non-blocking advisory, kept distinct from
    # ``blocking_modelo_references`` (no-silent-under-declaration).
    stale_draft_revision_references: tuple[LedgerRemovalBlocker, ...] = ()
    bucket_event_ids: tuple[str, ...] = ()


class LedgerExportCommand(BaseModel):
    """Backend command for exporting one bucket's canonical ledger rows."""

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    export_format: ExportSerializationFormat = ExportSerializationFormat.CSV
    include_inactive: bool = False
    output_path: Path | None = None
    # Optional period filter, carried as a typed :class:`Period` date span built
    # from the ``(--year, AEAT token)`` pair: restrict the export to rows whose
    # effective date falls in the period, so an operator can hand a gestor just
    # the quarter/year. None exports the whole bucket.
    period: Period | None = None
    actor: str = Field(default="operator", min_length=1, max_length=64)
    source_command: str = Field(default="aeat app ledger export", min_length=1, max_length=128)

    @field_validator("bucket_id", "actor", "source_command")
    @classmethod
    def _trim_required_text(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise TransactionValidationError("ledger export command text fields must not be blank")
        return trimmed


class BulkClassifyRow(BaseModel):
    """One row from a ``ledger classify --file`` CSV input file.

    Required columns: ``transaction_id``, ``classification``.
    Optional columns: ``category_id``, ``business_pct``, ``usage_ratio_id``,
    ``taxable_base``, ``iva_rate``, ``iva_amount``, ``iva_category``,
    ``irpf_category``.
    Unknown column names are rejected pre-persistence to protect against
    silent field mis-mapping. The IVA facts (``taxable_base``, ``iva_rate``,
    ``iva_amount``) are typed ``Decimal`` exactly as the single-classify path
    coerces them, so a malformed value reds the row rather than coercing
    silently.
    """

    model_config = _STRICT_FROZEN

    transaction_id: TransactionId
    classification: BusinessClassification
    category_id: str | None = None
    business_pct: Decimal | None = None
    usage_ratio_id: str | None = None
    taxable_base: Decimal | None = None
    iva_rate: Decimal | None = None
    iva_amount: Decimal | None = None
    iva_category: IvaCategory | None = None
    irpf_category: str | None = None


class BulkClassifyFailure(BaseModel):
    """One failed row from a ``ledger classify --file`` operation."""

    model_config = _STRICT_FROZEN

    row_index: int = Field(ge=0)
    transaction_id: str
    reason: str = Field(min_length=1)


class BulkClassifyResult(BaseModel):
    """Aggregate result for a ``ledger classify --file`` operation.

    Uses partial-success semantics matching the ledger import pattern:
    all parseable rows that pass validation are applied; failures are
    collected into ``failures`` and reported without aborting the batch.
    """

    model_config = _STRICT_FROZEN

    total: int = Field(ge=0)
    applied: int = Field(ge=0)
    skipped: int = Field(ge=0)
    failures: tuple[BulkClassifyFailure, ...] = ()
    bucket_event_ids: tuple[str, ...] = ()


BULK_CLASSIFY_ALLOWED_COLUMNS: frozenset[str] = frozenset(
    {
        "transaction_id",
        "classification",
        "category_id",
        "business_pct",
        "usage_ratio_id",
        "taxable_base",
        "iva_rate",
        "iva_amount",
        "iva_category",
        "irpf_category",
    },
)


class ApplyRulesAppliedRow(BaseModel):
    """One successfully rule-applied transaction from ``ledger rule apply``."""

    model_config = _STRICT_FROZEN

    transaction_id: TransactionId
    matched_rule_id: str = Field(min_length=1)
    classification: BusinessClassification


class ApplyRulesResult(BaseModel):
    """Aggregate result for a ``ledger rule apply`` operation."""

    model_config = _STRICT_FROZEN

    rules_evaluated: int = Field(ge=0)
    transactions_scanned: int = Field(ge=0)
    matched: int = Field(ge=0)
    skipped_already_classified: int = Field(ge=0)
    no_match: int = Field(ge=0)
    applied: tuple[ApplyRulesAppliedRow, ...] = ()
    bucket_event_ids: tuple[str, ...] = ()


class LedgerExportRow(BaseModel):
    """One serialized ledger transaction row exported from the canonical catalogue."""

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    transaction_id: TransactionId
    lifecycle_state: str = Field(min_length=1)
    booked_date: str = Field(min_length=10, max_length=10)
    value_date: str = ""
    effective_date: str = Field(min_length=10, max_length=10)
    amount: str = Field(min_length=1)
    currency: str = Field(min_length=3, max_length=3)
    direction: str = Field(min_length=1)
    counterparty: str = ""
    description: str = Field(min_length=1)
    business_classification: str = Field(min_length=1)
    business_pct: str = ""
    category_id: str = ""
    taxable_base: str = ""
    iva_rate: str = ""
    iva_amount: str = ""
    iva_category: str = ""
    counterparty_country: str = ""
    counterparty_identification_state: str = ""
    irpf_category: str = ""
    usage_ratio_id: str = ""
    prorrata_reference: str = ""
    purchase_invoice_evidence_id: str = ""
    attachment_ids: str = ""
    notes: str = ""
    created_by: str = ""
    created_source_command: str = ""
    source_jurisdiction: str = ""
    # FX provenance on the export hand-off: EUR
    # magnitude + applied CCY->EUR rate for foreign rows; "" for EUR-native rows.
    value_in_eur: str = ""
    fx_rate: str = ""


class LedgerExportResult(BaseModel):
    """Backend result for an exported canonical ledger transaction snapshot."""

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    export_id: Hex64Str
    export_format: ExportSerializationFormat
    media_type: str = Field(min_length=1)
    filename_extension: str = Field(min_length=1)
    row_count: int = Field(ge=0)
    byte_size: int = Field(ge=0)
    sha256: ContentDigest
    fieldnames: tuple[str, ...]
    rows: tuple[LedgerExportRow, ...]
    payload: bytes
    bucket_event_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _metadata_describes_the_payload(self) -> Self:
        """Refuse a result whose metadata contradicts the bytes it carries.

        These seven fields are redeclared here independently of
        :class:`~application.export.TabularExportResult`, which produces them,
        so this copy could disagree with its own payload even when the
        producer's did not. The export action anchors ``row_count``,
        ``byte_size`` and ``sha256`` into a durable
        ``LEDGER_TRANSACTION_EXPORTED`` bucket event, where a false value
        outlives the payload that would disprove it.

        Verified through the export package's one
        :func:`~application.export.verify_export_metadata` contract rather
        than a second local re-derivation.

        Raises:
            ExportFieldError: A metadata value disagrees with the payload.
        """
        verify_export_metadata(
            payload=self.payload,
            export_format=self.export_format,
            byte_size=self.byte_size,
            sha256=self.sha256,
            media_type=self.media_type,
            filename_extension=self.filename_extension,
            row_count=self.row_count,
        )
        return self


__all__ = [
    "BULK_CLASSIFY_ALLOWED_COLUMNS",
    "ApplyRulesAppliedRow",
    "ApplyRulesResult",
    "BulkClassifyFailure",
    "BulkClassifyResult",
    "BulkClassifyRow",
    "LedgerCatalogueResetReport",
    "LedgerExportCommand",
    "LedgerExportResult",
    "LedgerExportRow",
    "LedgerImportDiagnosticReport",
    "LedgerImportOperationResult",
    "LedgerRemovalBlocker",
    "LedgerReviewQuery",
    "LedgerReviewQueryResult",
    "LedgerReviewRow",
    "LedgerSourceImportCommand",
    "LedgerSourceImportResult",
    "LedgerSourceValidationReport",
    "LedgerSourceVerificationReport",
    "LedgerStatusReport",
    "LedgerTransactionPayload",
    "LedgerTransactionRemovalReport",
    "LedgerTransactionResultPayload",
    "LedgerTransactionReviewPayload",
    "LedgerTransactionTrackingPayload",
    "ManualLedgerTransactionCommand",
    "ManualLedgerTransactionPatch",
    "ManualLedgerTransactionResult",
    "MergeTransactionsResult",
    "SplitChildCommand",
    "SplitTransactionResult",
]
