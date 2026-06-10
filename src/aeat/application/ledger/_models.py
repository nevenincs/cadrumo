"""Strict Pydantic contracts for manual ledger transaction workflows."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Self

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core._models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN

# CLASSIFIED_BY_MANUAL is re-exported for constants centralisation tests.
from ...core.external_constants import (
    CLASSIFIED_BY_MANUAL as CLASSIFIED_BY_MANUAL,
)
from ...core.external_constants import (
    DEFAULT_CURRENCY,
)
from ...core.identity import BucketId, TransactionId
from ...domain.iva._schema import EUMemberState, IvaCategory
from ...domain.modelos._ids import CalculationRevisionId, WorkUnitId
from ...domain.transactions import (
    BucketTransactionRef,
    BusinessClassification,
    ImportSummary,
    Transaction,
    TransactionDirection,
    TransactionValidationError,
)
from ...domain.transactions._models import (
    TransactionEditLineageEntry,
    TransactionEvidenceProvenanceEntry,
    TransactionLifecycleLineageEntry,
)
from ..export import ExportSerializationFormat
from ..review import LedgerReviewStatus

_TRANSFER_ALLOWED_STATES = frozenset(
    {
        BusinessClassification.NOT_YET_PROCESSED,
        BusinessClassification.PERSONAL,
        BusinessClassification.PROCESSED_UNCLASSIFIED,
        BusinessClassification.SKIPPED_BY_RULE,
    }
)


def _validate_iso_3166_jurisdiction(value: str | None) -> str | None:
    """Validate and normalise a ``source_jurisdiction`` field value.

    Accepts ``None`` (no jurisdiction declared) or a two-letter
    ISO 3166-1 alpha-2 uppercase country code such as ``"ES"`` or ``"DE"``.
    Strips surrounding whitespace before the check; raises :class:`ValueError`
    if the result is not exactly two ASCII alphabetic uppercase characters.

    Used by :class:`ManualLedgerTransactionCommand`,
    :class:`ManualLedgerTransactionPatch`, :class:`LedgerTransactionPayload`,
    and :class:`LedgerTransactionReviewPayload` as a shared ``@field_validator``
    body, replacing four identical inline copies.
    """
    if value is None:
        return None
    normalised = value.strip()
    if len(normalised) != 2 or not normalised.isalpha() or normalised != normalised.upper():
        raise ValueError("source_jurisdiction must be a two-letter ISO 3166-1 alpha-2 uppercase code")
    return normalised


class ManualLedgerTransactionCommand(BaseModel):
    """Backend command for creating or updating one manual ledger transaction."""

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    booked_date: date
    value_date: date | None = None
    amount: Decimal
    currency: str = Field(default=DEFAULT_CURRENCY, min_length=3)
    direction: TransactionDirection
    counterparty: str | None = None
    description: str = Field(min_length=1)
    business_classification: BusinessClassification = BusinessClassification.NOT_YET_PROCESSED
    business_pct: Decimal | None = None
    category_id: str | None = None
    taxable_base: Decimal | None = None
    iva_rate: Decimal | None = None
    iva_amount: Decimal | None = None
    irpf_category: str | None = None
    usage_ratio_id: str | None = None
    prorrata_reference: str | None = None
    purchase_invoice_evidence_id: str | None = None
    attachment_ids: tuple[str, ...] = ()
    notes: str = ""
    iva_category: IvaCategory | None = None
    counterparty_eu_member_state: EUMemberState | None = None
    actor: str = Field(default="operator", min_length=1)
    source_command: str = Field(default="aeat app ledger add", min_length=1)
    idempotency_key: str | None = None
    classified_by_override: str | None = None
    source_jurisdiction: str | None = None
    group_label: str | None = Field(default=None, max_length=64)

    @field_validator("source_jurisdiction")
    @classmethod
    def _validate_source_jurisdiction(cls, value: str | None) -> str | None:
        return _validate_iso_3166_jurisdiction(value)

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

    @field_validator(
        "counterparty",
        "category_id",
        "irpf_category",
        "usage_ratio_id",
        "prorrata_reference",
        "purchase_invoice_evidence_id",
        "idempotency_key",
        "classified_by_override",
    )
    @classmethod
    def _trim_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None

    @field_validator("currency", mode="before")
    @classmethod
    def _normalise_currency(cls, value: object) -> str:
        normalised = str(value).strip().upper()
        if len(normalised) != 3 or not normalised.isalpha():
            raise ValueError("currency must be a three-letter ISO 4217 code")
        return normalised

    @field_validator("attachment_ids")
    @classmethod
    def _normalise_identifier_tuple(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalised = tuple(item.strip() for item in value if item.strip())
        if len(set(normalised)) != len(normalised):
            raise ValueError("identifier tuple must not contain duplicates")
        return normalised

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
        if self.amount == Decimal("0"):
            raise TransactionValidationError(
                "manual ledger transaction amount must be non-zero; attach zero-value evidence to an existing row"
            )
        if self.direction is TransactionDirection.OUTGOING and self.amount >= Decimal("0"):
            raise TransactionValidationError("OUTGOING manual ledger transactions require a negative amount")
        if self.direction is TransactionDirection.INCOMING and self.amount <= Decimal("0"):
            raise TransactionValidationError("INCOMING manual ledger transactions require a positive amount")
        if self.direction is TransactionDirection.INTERNAL_TRANSFER:
            self._validate_internal_transfer_payload()
        return self

    def _validate_internal_transfer_payload(self) -> None:
        if self.business_classification not in _TRANSFER_ALLOWED_STATES:
            raise TransactionValidationError(
                "INTERNAL_TRANSFER rows must not be classified as tax-relevant business rows"
            )
        forbidden = {
            "category_id": self.category_id,
            "taxable_base": self.taxable_base,
            "iva_rate": self.iva_rate,
            "iva_amount": self.iva_amount,
            "irpf_category": self.irpf_category,
            "usage_ratio_id": self.usage_ratio_id,
            "prorrata_reference": self.prorrata_reference,
            "purchase_invoice_evidence_id": self.purchase_invoice_evidence_id,
            "attachment_ids": self.attachment_ids,
        }
        populated = tuple(key for key, value in forbidden.items() if value not in (None, ()))
        if populated:
            joined = ", ".join(populated)
            raise TransactionValidationError(f"INTERNAL_TRANSFER rows must not carry tax or evidence fields: {joined}")


class ManualLedgerTransactionPatch(BaseModel):
    """Typed partial update for one bucket-scoped ledger transaction."""

    model_config = _STRICT_FROZEN

    booked_date: date | None = None
    value_date: date | None = None
    amount: Decimal | None = None
    currency: str | None = None
    direction: TransactionDirection | None = None
    counterparty: str | None = None
    description: str | None = None
    business_classification: BusinessClassification | None = None
    business_pct: Decimal | None = None
    category_id: str | None = None
    taxable_base: Decimal | None = None
    iva_rate: Decimal | None = None
    iva_amount: Decimal | None = None
    irpf_category: str | None = None
    usage_ratio_id: str | None = None
    prorrata_reference: str | None = None
    purchase_invoice_evidence_id: str | None = None
    attachment_ids: tuple[str, ...] | None = None
    notes: str | None = None
    iva_category: IvaCategory | None = None
    counterparty_eu_member_state: EUMemberState | None = None
    source_jurisdiction: str | None = None
    group_label: str | None = None

    @field_validator("source_jurisdiction")
    @classmethod
    def _validate_source_jurisdiction(cls, value: str | None) -> str | None:
        return _validate_iso_3166_jurisdiction(value)

    @field_validator(
        "counterparty",
        "description",
        "category_id",
        "irpf_category",
        "usage_ratio_id",
        "prorrata_reference",
        "purchase_invoice_evidence_id",
        "notes",
        "group_label",
    )
    @classmethod
    def _trim_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None

    @field_validator("currency", mode="before")
    @classmethod
    def _normalise_optional_currency(cls, value: object) -> str | None:
        if value is None:
            return None
        return ManualLedgerTransactionCommand._normalise_currency(value)

    @field_validator("attachment_ids")
    @classmethod
    def _normalise_optional_identifier_tuple(cls, value: tuple[str, ...] | None) -> tuple[str, ...] | None:
        if value is None:
            return None
        return ManualLedgerTransactionCommand._normalise_identifier_tuple(value)

    @model_validator(mode="after")
    def _require_change(self) -> Self:
        if not self.model_fields_set:
            raise TransactionValidationError("manual ledger patch must carry at least one field")
        return self


class ManualLedgerTransactionResult(BaseModel):
    """Backend result for a persisted manual ledger transaction mutation."""

    model_config = _STRICT_FROZEN

    ref: BucketTransactionRef
    transaction: Transaction
    bucket_event_ids: tuple[str, ...] = ()


class LedgerTransactionPayload(BaseModel):
    """Canonical read projection for one ledger transaction."""

    model_config = _STRICT_FROZEN

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
    irpf_category: str | None = None
    usage_ratio_id: str | None = None
    prorrata_reference: str | None = None
    purchase_invoice_evidence_id: str | None = None
    attachment_ids: tuple[str, ...] = ()
    notes: str = ""
    lifecycle_state: str = Field(min_length=1)
    classified_by: str = Field(min_length=1)
    source_jurisdiction: str | None = None
    # FX provenance for foreign-currency rows (ledger-fx-conversion ADR): the
    # EUR-equivalent and the applied CCY->EUR rate, so list/review/export surface
    # the converted value rather than only the native amount. None for EUR rows.
    value_in_eur: str | None = None
    fx_rate: str | None = None

    @field_validator("source_jurisdiction")
    @classmethod
    def _validate_source_jurisdiction(cls, value: str | None) -> str | None:
        return _validate_iso_3166_jurisdiction(value)


class LedgerTransactionReviewPayload(BaseModel):
    """Canonical read projection for one ledger transaction plus review status."""

    model_config = _STRICT_FROZEN

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
    irpf_category: str | None = None
    usage_ratio_id: str | None = None
    prorrata_reference: str | None = None
    purchase_invoice_evidence_id: str | None = None
    attachment_ids: tuple[str, ...] = ()
    notes: str = ""
    lifecycle_state: str = Field(min_length=1)
    review_status: LedgerReviewStatus
    classified_by: str = Field(min_length=1)
    source_jurisdiction: str | None = None
    # FX provenance (ledger-fx-conversion ADR): EUR-equivalent + applied
    # CCY->EUR rate for foreign rows; None for EUR-native rows.
    value_in_eur: str | None = None
    fx_rate: str | None = None

    @field_validator("source_jurisdiction")
    @classmethod
    def _validate_source_jurisdiction(cls, value: str | None) -> str | None:
        return _validate_iso_3166_jurisdiction(value)


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
        amount: Signed Decimal in the parent's currency. Must agree
            with the parent's direction sign convention (positive for
            INCOMING, negative for OUTGOING).
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
    split_group_id: str = Field(min_length=64, max_length=64)
    child_transaction_ids: tuple[str, ...]
    parent_transaction: Transaction
    child_transactions: tuple[Transaction, ...]
    bucket_event_id: str = Field(min_length=64, max_length=64)


class MergeTransactionsResult(BaseModel):
    """Backend result of a successful split re-merge."""

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    split_group_id: str = Field(min_length=64, max_length=64)
    parent_transaction_id: TransactionId
    merged_transaction_id: TransactionId
    source_child_ids: tuple[str, ...]
    merged_transaction: Transaction
    parent_transaction: Transaction
    bucket_event_id: str = Field(min_length=64, max_length=64)


class LedgerImportOperationResult(BaseModel):
    """Backend result for an imported ledger transaction batch."""

    model_config = _STRICT_FROZEN

    summary: ImportSummary
    import_batch_id: str | None = Field(default=None, min_length=64, max_length=64)
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
    period: str | None = None
    actor: str = Field(default="operator", min_length=1, max_length=64)
    source_command: str = Field(default="aeat app ledger import", min_length=1, max_length=128)

    @field_validator("bucket_id", "provider", "period", "actor", "source_command")
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
    period: str | None = None
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
    period: str | None = None
    status: str | None = None
    issue: str | None = None
    import_id: str | None = None
    classification: str | None = None
    text: str | None = None
    direction: str | None = None
    transaction_id: str | None = Field(default=None, min_length=64, max_length=64)

    @field_validator(
        "bucket_id", "period", "status", "issue", "import_id", "classification", "text", "direction", "transaction_id"
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
    """Backend projection for one ledger review row."""

    model_config = _STRICT_FROZEN

    id: str = Field(min_length=64, max_length=64)
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
    # calculation). Default "0.00" for legacy reports.
    income_total: str = "0.00"
    expense_total: str = "0.00"
    net_total: str = "0.00"
    total_count: int = Field(ge=0)
    active_count: int = Field(ge=0)
    archived_count: int = Field(ge=0)
    stashed_count: int = Field(ge=0)
    split_count: int = Field(ge=0, default=0)
    pending_review_count: int = Field(ge=0)
    reviewed_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    period: str | None = None
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
    bucket_event_ids: tuple[str, ...] = ()


class LedgerExportCommand(BaseModel):
    """Backend command for exporting one bucket's canonical ledger rows."""

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    export_format: ExportSerializationFormat = ExportSerializationFormat.CSV
    include_inactive: bool = False
    output_path: Path | None = None
    # Optional period filter (e.g. "2025Q1", "2025"): restrict the export to rows
    # whose effective date falls in the period, so an operator can hand a gestor
    # just the quarter/year. None exports the whole bucket.
    period: str | None = None
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
    """One row from a ``ledger classify --from-csv`` CSV input file.

    Required columns: ``transaction_id``, ``classification``.
    Optional columns: ``category_id``, ``business_pct``, ``taxable_base``,
    ``iva_rate``, ``iva_amount``.
    Unknown column names are rejected pre-persistence to protect against
    silent field mis-mapping. The IVA facts (``taxable_base``, ``iva_rate``,
    ``iva_amount``) are typed ``Decimal`` exactly as the single-classify path
    coerces them, so a malformed value reds the row rather than coercing
    silently.
    """

    model_config = _STRICT_FROZEN

    transaction_id: str = Field(min_length=1)
    classification: BusinessClassification
    category_id: str | None = None
    business_pct: Decimal | None = None
    taxable_base: Decimal | None = None
    iva_rate: Decimal | None = None
    iva_amount: Decimal | None = None


class BulkClassifyFailure(BaseModel):
    """One failed row from a ``ledger classify --from-csv`` operation."""

    model_config = _STRICT_FROZEN

    row_index: int = Field(ge=0)
    transaction_id: str
    reason: str = Field(min_length=1)


class BulkClassifyResult(BaseModel):
    """Aggregate result for a ``ledger classify --from-csv`` operation.

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
        "taxable_base",
        "iva_rate",
        "iva_amount",
    }
)


class ApplyRulesAppliedRow(BaseModel):
    """One successfully rule-applied transaction from ``ledger rule apply``."""

    model_config = _STRICT_FROZEN

    transaction_id: str = Field(min_length=1)
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
    irpf_category: str = ""
    usage_ratio_id: str = ""
    prorrata_reference: str = ""
    purchase_invoice_evidence_id: str = ""
    attachment_ids: str = ""
    notes: str = ""
    created_by: str = ""
    created_source_command: str = ""
    source_jurisdiction: str = ""
    # FX provenance on the export hand-off (ledger-fx-conversion ADR): EUR
    # magnitude + applied CCY->EUR rate for foreign rows; "" for EUR-native rows.
    value_in_eur: str = ""
    fx_rate: str = ""


class LedgerExportResult(BaseModel):
    """Backend result for an exported canonical ledger transaction snapshot."""

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    export_id: str = Field(min_length=64, max_length=64)
    export_format: ExportSerializationFormat
    media_type: str = Field(min_length=1)
    filename_extension: str = Field(min_length=1)
    row_count: int = Field(ge=0)
    byte_size: int = Field(ge=0)
    sha256: str = Field(min_length=64, max_length=64)
    fieldnames: tuple[str, ...]
    rows: tuple[LedgerExportRow, ...]
    payload: bytes
    bucket_event_ids: tuple[str, ...] = ()
