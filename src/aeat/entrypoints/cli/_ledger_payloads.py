"""Typed ``--json`` payload schemas for ledger CLI commands.

Each class declared here is a strict :class:`OutputSchema` subclass and is
decorated with :func:`register_schema` so the JSON-contract test suite can
enumerate every ledger-command surface this module covers.

Field sets match the production payload dicts constructed in ``_ledger.py``
at their emit sites. Optional fields cover multi-branch payload shapes
(e.g. ledger.classify has a bulk path and a single-transaction path;
ledger.import carries optional dry-run and duplicate-warning notices).

All sequence fields use ``list`` rather than ``tuple`` because
``model_dump(mode='json')`` serialises pydantic tuples as JSON arrays, and
the strict ``OutputSchema`` base does not coerce lists to tuples on
re-validation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._schemas import OutputSchema, register_schema

if TYPE_CHECKING:
    from ...application.inventory import InventoryValuationPreviewResult as _AppInventoryValuationPreviewResult
    from ...application.ledger import LedgerExportResult as _AppLedgerExportResult
    from ...application.ledger import LedgerSourceImportResult as _AppLedgerSourceImportResult

# ---------------------------------------------------------------------------
# Shared sub-models (not registered — used as nested types)
# ---------------------------------------------------------------------------


class TransactionPayload(OutputSchema):
    """Canonical read projection for one ledger transaction (nested)."""

    transaction_id: str
    date: str
    booked_date: str
    value_date: str | None = None
    amount: str
    currency: str
    direction: str
    counterparty: str = ""
    description: str
    business_classification: str
    business_pct: str | None = None
    category_id: str | None = None
    taxable_base: str | None = None
    iva_rate: str | None = None
    iva_amount: str | None = None
    irpf_category: str | None = None
    usage_ratio_id: str | None = None
    prorrata_reference: str | None = None
    purchase_invoice_evidence_id: str | None = None
    attachment_ids: list[str] = []
    notes: str = ""
    lifecycle_state: str
    classified_by: str
    source_jurisdiction: str | None = None
    # FX provenance for foreign-currency rows (ledger-fx-conversion ADR): the
    # EUR-equivalent and applied CCY->EUR rate the application payload now emits.
    # Declared here so the strict single-transaction read surface (ledger
    # view/classify --id/update/archive/stash) accepts the persisted FX fields
    # rather than rejecting them as extra_forbidden. None for EUR-native rows.
    value_in_eur: str | None = None
    fx_rate: str | None = None


class BulkClassifyFailurePayload(OutputSchema):
    """One failed row from a bulk classify operation."""

    row_index: int
    transaction_id: str
    reason: str


class SpendingCategoryFamilyPayload(OutputSchema):
    """One spending category family entry in the categories catalogue."""

    family: str
    category_ids: list[str]


class LedgerReviewRowPayload(OutputSchema):
    """One ledger review row."""

    id: str
    date: str
    amount: str
    description: str
    status: str
    transaction: TransactionPayload | None = None


class LedgerRemovalBlockerPayload(OutputSchema):
    """One modelo revision that blocks ledger transaction removal."""

    work_unit_id: str
    calculation_revision_id: str
    revision_state: str
    modelo: str
    filing_year: int
    period: str


class LedgerImportValidationPayload(OutputSchema):
    """Source-file validation details nested in import result."""

    valid: bool
    warnings: list[str] = []
    encoding: str | None = None
    dialect: str | None = None


class LedgerImportSourcePayload(OutputSchema):
    """Source-file verification details nested in import result."""

    requested: bool
    path: str | None = None
    sha256: str | None = None


class LedgerImportDiagnosticPayload(OutputSchema):
    """One import diagnostic entry."""

    kind: str
    severity: str
    message: str
    source_path: str | None = None
    source_locator: str | None = None
    affected_transaction_ids: list[str] = []


class LedgerSplitChildProposalPayload(OutputSchema):
    """One proposed child of an evidence-driven LLM split (preview surface).

    The model proposed the ``proportion`` and selected the ``category`` /
    ``iva_category``; the system DERIVED the euro ``amount`` and the regulated
    ``iva_rate`` / ``taxable_base`` / ``iva_amount`` from the registry. Numbers
    are JSON strings to preserve ``~decimal.Decimal`` precision.
    """

    proportion: str
    amount: str
    description: str
    category: str | None = None
    iva_category: str | None = None
    iva_rate: str | None = None
    taxable_base: str | None = None
    iva_amount: str | None = None
    rate_derivable: bool = False


# ---------------------------------------------------------------------------
# P01 — Mutation verb result schemas
# ---------------------------------------------------------------------------


@register_schema("ledger.add")
class LedgerAddResult(OutputSchema):
    """JSON envelope for ``aeat app ledger add``."""

    bucket_id: str
    transaction_id: str
    bucket_event_ids: list[str]
    transaction: TransactionPayload


class _LedgerMutationResult(OutputSchema):
    """Shared shape for single-transaction mutation verbs.

    Subclassed per verb so each registers its own schema path.
    """

    bucket_id: str
    transaction_id: str
    bucket_event_ids: list[str]
    review_status: str
    transaction: TransactionPayload


@register_schema("ledger.update")
class LedgerUpdateResult(_LedgerMutationResult):
    """JSON envelope for ``aeat app ledger update``."""


@register_schema("ledger.classify")
class LedgerClassifyResult(OutputSchema):
    """JSON envelope for ``aeat app ledger classify``.

    Covers both the single-transaction path and the bulk ``--from-csv`` path.
    All fields are optional so both branches validate cleanly.
    """

    # Single-transaction path fields
    bucket_id: str | None = None
    transaction_id: str | None = None
    bucket_event_ids: list[str] | None = None
    review_status: str | None = None
    transaction: TransactionPayload | None = None
    # Bulk --from-csv path fields
    total: int | None = None
    applied: int | None = None
    skipped: int | None = None
    failures: list[BulkClassifyFailurePayload] | None = None
    # LLM suggest path fields (--llm without --apply): the proposed decision is
    # surfaced for operator review; nothing is persisted. ``applied`` stays
    # False until the operator re-runs with ``--apply``.
    llm: bool | None = None
    provider: str | None = None
    classification: str | None = None
    category: str | None = None
    confidence: str | None = None
    reason: str | None = None
    provenance: str | None = None
    persisted: bool | None = None
    # Saturation path fields (--llm --saturate): the model-selected IVA category
    # plus the system-derived euro substrate. The numbers are present only when
    # the category was derivable; otherwise ``derivation_note`` explains why the
    # operator must complete them.
    iva_category: str | None = None
    iva_rate: str | None = None
    taxable_base: str | None = None
    iva_amount: str | None = None
    rate_derivable: bool | None = None
    derivation_note: str | None = None


@register_schema("ledger.allocate")
class LedgerAllocateResult(_LedgerMutationResult):
    """JSON envelope for ``aeat app ledger allocate``."""


@register_schema("ledger.attach")
@register_schema("ledger.doclink")
class LedgerAttachResult(_LedgerMutationResult):
    """JSON envelope for ``aeat app ledger attach`` and ``ledger doclink``."""


@register_schema("ledger.archive")
class LedgerArchiveResult(_LedgerMutationResult):
    """JSON envelope for ``aeat app ledger archive``."""


@register_schema("ledger.stash")
class LedgerStashResult(_LedgerMutationResult):
    """JSON envelope for ``aeat app ledger stash``."""


@register_schema("ledger.restore")
class LedgerRestoreResult(_LedgerMutationResult):
    """JSON envelope for ``aeat app ledger restore``."""


@register_schema("ledger.remove")
class LedgerRemoveResult(OutputSchema):
    """JSON envelope for ``aeat app ledger remove``.

    Mirrors ``LedgerTransactionRemovalReport.model_dump(mode='json')``.
    """

    bucket_id: str
    transaction_id: str
    removed: bool = False
    dry_run: bool = False
    actor: str
    reason: str = ""
    cascaded_purchase_invoice_evidence_ids: list[str] = []
    cascaded_attachment_ids: list[str] = []
    blocking_modelo_references: list[LedgerRemovalBlockerPayload] = []
    bucket_event_ids: list[str] = []


@register_schema("ledger.reset")
class LedgerResetResult(OutputSchema):
    """JSON envelope for ``aeat app ledger reset``.

    Mirrors ``LedgerCatalogueResetReport.model_dump(mode='json')``.
    """

    bucket_id: str
    removed_transaction_ids: list[str] = []
    reset: bool = False
    dry_run: bool = False
    actor: str
    reason: str = ""
    cascaded_purchase_invoice_evidence_ids: list[str] = []
    cascaded_attachment_ids: list[str] = []
    blocking_modelo_references: list[LedgerRemovalBlockerPayload] = []
    bucket_event_ids: list[str] = []


@register_schema("ledger.split")
class LedgerSplitResult(OutputSchema):
    """JSON envelope for ``aeat app ledger split``.

    Covers the manual split (explicit ``--child-amount`` / ``--child-description``)
    and the evidence-driven LLM split (``--llm``). On the LLM preview path
    (``--llm`` without ``--apply``) ``persisted`` is False, nothing is written, and
    ``proposed_children`` carries the derived child amounts for review; the
    structural ``split_group_id`` / ``bucket_event_id`` appear only once a split is
    actually persisted.
    """

    bucket_id: str
    parent_transaction_id: str
    split_group_id: str | None = None
    child_transaction_ids: list[str] = []
    bucket_event_id: str | None = None
    # LLM evidence-driven path (--llm)
    llm: bool | None = None
    persisted: bool | None = None
    provider: str | None = None
    provenance: str | None = None
    reason: str | None = None
    parent_amount: str | None = None
    proposed_children: list[LedgerSplitChildProposalPayload] | None = None
    classified_child_count: int | None = None


@register_schema("ledger.merge")
class LedgerMergeResult(OutputSchema):
    """JSON envelope for ``aeat app ledger merge``."""

    bucket_id: str
    split_group_id: str
    parent_transaction_id: str
    merged_transaction_id: str
    source_child_ids: list[str]
    bucket_event_id: str


# ---------------------------------------------------------------------------
# P02 — Query verb result schemas
# ---------------------------------------------------------------------------


@register_schema("ledger.list")
class LedgerListResult(OutputSchema):
    """JSON envelope for ``aeat app ledger list``.

    ``rows`` is the page actually rendered; ``total`` is the full bucket row
    count. When ``--limit`` clips the page, ``truncated`` is ``True`` and
    ``offset`` / ``limit`` describe the window so a large ledger is never
    silently capped — the consumer can always see that more rows exist.
    """

    bucket_id: str
    rows: list[dict[str, object]]
    total: int = 0
    shown: int = 0
    offset: int = 0
    limit: int | None = None
    truncated: bool = False


@register_schema("ledger.view")
class LedgerViewResult(OutputSchema):
    """JSON envelope for ``aeat app ledger view``.

    Mirrors ``LedgerTransactionResultPayload``.
    """

    bucket_id: str
    transaction_id: str
    review_status: str
    transaction: TransactionPayload


@register_schema("ledger.status")
class LedgerStatusResult(OutputSchema):
    """JSON envelope for ``aeat app ledger status``.

    Mirrors ``LedgerStatusReport.model_dump(mode='json')``.
    """

    bucket_id: str
    income_total: str = "0.00"
    expense_total: str = "0.00"
    net_total: str = "0.00"
    total_count: int
    active_count: int
    archived_count: int
    stashed_count: int
    split_count: int = 0
    pending_review_count: int
    reviewed_count: int
    skipped_count: int
    # The filing period travels as a typed :class:`Period` date span on the
    # backend report; the JSON envelope surfaces its serialised mapping (year,
    # quarter/month, start/end), mirroring ``LedgerPreflightResult.period``.
    period: dict[str, object] | None = None
    checked_transaction_count: int = 0
    readiness_issue_count: int = 0
    ready: bool | None = None


@register_schema("ledger.history")
class LedgerHistoryResult(OutputSchema):
    """JSON envelope for ``aeat app ledger history``."""

    bucket_id: str
    transaction_id: str
    event_count: int
    events: list[dict[str, object]]


@register_schema("ledger.categories")
class LedgerCategoriesResult(OutputSchema):
    """JSON envelope for ``aeat app ledger categories``."""

    families: list[SpendingCategoryFamilyPayload]
    category_ids: list[str]
    income_requires_category: bool


# ---------------------------------------------------------------------------
# P03 — Import / export / track / review verb result schemas
# ---------------------------------------------------------------------------


@register_schema("ledger.export")
class LedgerExportPayload(OutputSchema):
    """JSON envelope for ``aeat app ledger export``.

    Distinct from the application :class:`LedgerExportResult` (DB-26 S51): the
    backend result carries the raw ``payload`` bytes and typed members
    (``BucketId``, ``ExportSerializationFormat``, ``LedgerExportRow``); this
    envelope projects the JSON-coerced metadata + row view and appends the
    operator-facing ``output_path``. Derive instances via :meth:`from_result`.
    """

    bucket_id: str
    export_id: str
    export_format: str
    media_type: str
    filename_extension: str
    row_count: int
    byte_size: int
    sha256: str
    fieldnames: list[str]
    rows: list[dict[str, object]]
    bucket_event_ids: list[str] = []
    output_path: str

    @classmethod
    def from_result(cls, result: _AppLedgerExportResult, *, output_path: str) -> LedgerExportPayload:
        """Project the application export result into this CLI :class:`LedgerExportPayload` envelope.

        The raw ``payload`` bytes are excluded — the JSON envelope carries
        export metadata and the row projection, not the binary artefact (that
        is written to ``output_path``). ``model_dump(mode="json")`` performs the
        typed-id/enum/nested-row coercion so the envelope's loosened field types
        stay exactly consistent with the backend contract.
        """
        data = result.model_dump(mode="json", exclude={"payload"})
        data["output_path"] = output_path
        return cls.model_validate(data)


@register_schema("ledger.import")
class LedgerImportPayload(OutputSchema):
    """JSON envelope for ``aeat app ledger import``.

    Distinct from the application :class:`LedgerSourceImportResult` (DB-26 S51):
    this envelope projects that result's JSON-coerced fields (the nested
    validation/source/diagnostic reports become the CLI ``*Payload`` shapes) and
    appends the optional operator-facing notice strings. Derive instances via
    :meth:`from_result`.
    """

    rows: int
    imported: int
    skipped: int
    likely_duplicates: int = 0
    dry_run: bool
    verify: bool
    # The filing period travels as a typed :class:`Period` date span on the
    # backend result; the JSON envelope surfaces its serialised mapping.
    period: dict[str, object] | None = None
    bucket_id: str | None = None
    import_batch_id: str | None = None
    bucket_event_ids: list[str] = []
    imported_transaction_refs: list[dict[str, object]] = []
    skipped_transaction_refs: list[dict[str, object]] = []
    likely_duplicate_transaction_refs: list[dict[str, object]] = []
    validation: LedgerImportValidationPayload
    source: LedgerImportSourcePayload
    diagnostics: list[LedgerImportDiagnosticPayload] = []
    # Optional notice fields appended at the emit site
    dry_run_notice: str | None = None
    empty_import_notice: str | None = None
    likely_duplicate_notice: str | None = None

    @classmethod
    def from_result(
        cls,
        result: _AppLedgerSourceImportResult,
        *,
        dry_run_notice: str | None = None,
        empty_import_notice: str | None = None,
        likely_duplicate_notice: str | None = None,
    ) -> LedgerImportPayload:
        """Project the application import result into this CLI :class:`LedgerImportPayload` envelope.

        ``model_dump(mode="json")`` coerces the typed members (typed-ids, nested
        validation/source/diagnostic reports) to the JSON shape this envelope
        declares. The three notices are operator-facing display strings computed
        at the emit site and threaded through so this stays the single
        construction point; each is attached only when present.
        """
        data = result.model_dump(mode="json")
        if dry_run_notice is not None:
            data["dry_run_notice"] = dry_run_notice
        if empty_import_notice is not None:
            data["empty_import_notice"] = empty_import_notice
        if likely_duplicate_notice is not None:
            data["likely_duplicate_notice"] = likely_duplicate_notice
        return cls.model_validate(data)


@register_schema("ledger.participation.rebuild")
class LedgerParticipationRebuildResult(OutputSchema):
    """JSON envelope for ``aeat app ledger participation rebuild``.

    Reports the outcome of regenerating the transaction participation index from
    the finalized-revision catalogue.
    """

    transaction_count: int
    participation_count: int
    revision_count: int


@register_schema("ledger.track")
class LedgerTrackResult(OutputSchema):
    """JSON envelope for ``aeat app ledger track``."""

    bucket_id: str
    transaction: TransactionPayload
    tracking: dict[str, object]


@register_schema("ledger.review")
class LedgerReviewResult(OutputSchema):
    """JSON envelope for ``aeat app ledger review``.

    Covers three payload branches:
    - Multi-row list: ``rows`` + ``filters``
    - Empty-result (``--id`` with no match): empty ``rows`` + ``filters``
    - Single-row detail: scalar fields for the matched row

    All fields are optional so each discriminated path validates cleanly.
    """

    # Multi-row and empty-result paths
    rows: list[LedgerReviewRowPayload] | None = None
    filters: list[str] | None = None
    # Single-transaction detail path
    id: str | None = None
    date: str | None = None
    amount: str | None = None
    description: str | None = None
    review_status: str | None = None
    transaction: TransactionPayload | None = None
    verbose: bool | None = None


# ---------------------------------------------------------------------------
# P04 — Diagnostic verb result schemas (check / preflight / link)
# ---------------------------------------------------------------------------


class LedgerPreflightIssuePayload(OutputSchema):
    """One ledger preflight / check issue row (matches LedgerPreflightIssue.model_dump)."""

    transaction_id: str
    reason: str
    detail: str = ""


@register_schema("ledger.check")
class LedgerCheckResult(OutputSchema):
    """JSON envelope for ``aeat app ledger check``."""

    bucket_id: str
    periods: list[str]
    checked_transaction_count: int
    issues: list[LedgerPreflightIssuePayload]
    ready: bool


@register_schema("ledger.preflight")
class LedgerPreflightResult(OutputSchema):
    """JSON envelope for ``aeat app ledger preflight``.

    Mirrors ``LedgerPreflightReport.model_dump(mode='json')`` produced
    by :func:`preflight_ledger_tax_readiness`. ``period`` is the nested
    :class:`Period` model dump; ``ready`` is the computed-field flag.
    """

    bucket_id: str
    period: dict[str, object]
    checked_transaction_count: int
    issues: list[dict[str, object]]
    ready: bool


@register_schema("ledger.link")
class LedgerLinkResult(OutputSchema):
    """JSON envelope for ``aeat app ledger link``."""

    operation: str
    bucket_id: str
    transaction_id: str
    invoice_id: str | None = None
    evidence_id: str | None = None
    actor: str
    evidence_update: dict[str, object] | None = None


# ---------------------------------------------------------------------------
# P05 — Usage-ratios sub-app result schemas
# ---------------------------------------------------------------------------


class RatiosRowPayload(OutputSchema):
    """One per-category usage-ratio row."""

    category: str
    ratio: str


@register_schema("ledger.ratios.list")
class RatiosListResult(OutputSchema):
    """JSON envelope for ``aeat app ledger ratios list``."""

    bucket_id: str
    rows: list[RatiosRowPayload]
    count: int
    censo_mismatch: str | None = None


@register_schema("ledger.ratios.set")
class RatiosSetResult(OutputSchema):
    """JSON envelope for ``aeat app ledger ratios set``."""

    bucket_id: str
    category: str
    ratio: str


@register_schema("ledger.ratios.unset")
class RatiosUnsetResult(OutputSchema):
    """JSON envelope for ``aeat app ledger ratios unset``."""

    bucket_id: str
    category: str
    ratio: str = ""


@register_schema("ledger.ratios.eligible")
class RatiosEligibleResult(OutputSchema):
    """JSON envelope for ``aeat app ledger ratios eligible``."""

    bucket_id: str
    rows: list[dict[str, object]]
    count: int


@register_schema("ledger.ratios.validate")
class RatiosValidateResult(OutputSchema):
    """JSON envelope for ``aeat app ledger ratios validate``.

    Mirrors ``RatiosValidationReport.model_dump(mode='json')`` produced by
    :func:`validate_ratios_for_bucket`.
    """

    bucket_id: str
    profile_present: bool
    eligible_count: int
    overrides_count: int
    missing_overrides: list[str] = []
    findings: list[dict[str, object]] = []


# ---------------------------------------------------------------------------
# P06 — Business operation invoice sub-apps
# (payable-invoice and collectible-invoice share the same record shape)
# ---------------------------------------------------------------------------


class BusinessInvoiceRecordPayload(OutputSchema):
    """One business-operation invoice record.

    Mirrors ``BusinessOperationInvoiceRecord.model_dump(mode='json')``
    plus the ``bucket_event_ids`` field the CLI appends at the emit
    site for mutation verbs (defaults to empty for read verbs).
    """

    invoice_id: str
    bucket_id: str
    source_kind: str
    counterparty_nif: str
    counterparty_name: str = ""
    invoice_number: str
    invoice_date: str
    currency: str
    taxable_base: str
    iva_rate: str | None = None
    iva_amount: str
    total_amount: str
    notes: str = ""
    country_code: str | None = None
    eu_iva_id: str | None = None
    operation_type: str | None = None
    created_at: str
    updated_at: str
    bucket_event_ids: list[str] = []


class BusinessInvoiceListResult(OutputSchema):
    """Shared list result for payable / collectible invoice list verbs."""

    bucket_id: str
    rows: list[dict[str, object]]
    count: int


@register_schema("ledger.payable_invoice.add")
class PayableInvoiceAddResult(BusinessInvoiceRecordPayload):
    """JSON envelope for ``aeat app ledger payable-invoice add``."""


@register_schema("ledger.payable_invoice.view")
class PayableInvoiceViewResult(BusinessInvoiceRecordPayload):
    """JSON envelope for ``aeat app ledger payable-invoice view``."""


@register_schema("ledger.payable_invoice.update")
class PayableInvoiceUpdateResult(BusinessInvoiceRecordPayload):
    """JSON envelope for ``aeat app ledger payable-invoice update``."""


@register_schema("ledger.payable_invoice.remove")
class PayableInvoiceRemoveResult(BusinessInvoiceRecordPayload):
    """JSON envelope for ``aeat app ledger payable-invoice remove``."""


@register_schema("ledger.payable_invoice.list")
class PayableInvoiceListResult(BusinessInvoiceListResult):
    """JSON envelope for ``aeat app ledger payable-invoice list``."""


@register_schema("ledger.collectible_invoice.add")
class CollectibleInvoiceAddResult(BusinessInvoiceRecordPayload):
    """JSON envelope for ``aeat app ledger collectible-invoice add``."""


@register_schema("ledger.collectible_invoice.view")
class CollectibleInvoiceViewResult(BusinessInvoiceRecordPayload):
    """JSON envelope for ``aeat app ledger collectible-invoice view``."""


@register_schema("ledger.collectible_invoice.update")
class CollectibleInvoiceUpdateResult(BusinessInvoiceRecordPayload):
    """JSON envelope for ``aeat app ledger collectible-invoice update``."""


@register_schema("ledger.collectible_invoice.remove")
class CollectibleInvoiceRemoveResult(BusinessInvoiceRecordPayload):
    """JSON envelope for ``aeat app ledger collectible-invoice remove``."""


@register_schema("ledger.collectible_invoice.list")
class CollectibleInvoiceListResult(BusinessInvoiceListResult):
    """JSON envelope for ``aeat app ledger collectible-invoice list``."""


# ---------------------------------------------------------------------------
# P07 — Inventory sub-app
# ---------------------------------------------------------------------------


class InventoryLedgerPayload(OutputSchema):
    """One per-actividad inventory ledger record.

    Mirrors :class:`aeat.domain.contribuyente.inventory.InventoryLedger`'s
    ``model_dump(mode='json')`` plus the ``bucket_event_ids`` field the
    CLI appends at the emit site.
    """

    actividad_id: str
    year: int
    valuation_method: str
    opening_stock: str
    opening_layers: list[dict[str, object]] = []
    closing_stock: str | None = None
    period_movements: list[dict[str, object]] = []
    schema_version: str
    bucket_event_ids: list[str] = []


@register_schema("ledger.inventory.list")
class InventoryListResult(OutputSchema):
    """JSON envelope for ``aeat app ledger inventory list``."""

    bucket_id: str
    rows: list[dict[str, object]]
    count: int


@register_schema("ledger.inventory.create")
class InventoryCreateResult(InventoryLedgerPayload):
    """JSON envelope for ``aeat app ledger inventory create``."""


@register_schema("ledger.inventory.movement.add")
class InventoryMovementAddResult(InventoryLedgerPayload):
    """JSON envelope for ``aeat app ledger inventory movement add``."""


@register_schema("ledger.inventory.valuation.preview")
class InventoryValuationPreviewPayload(OutputSchema):
    """JSON envelope for ``aeat app ledger inventory valuation preview``.

    Distinct from the application wrapper :class:`InventoryValuationPreviewResult`
    (DB-26 S52): this envelope *flattens* that wrapper, projecting its inner
    ``preview`` (:class:`InventoryValuationPreview`) fields and lifting the
    wrapper's ``bucket_event_ids`` to the top level. Derive via :meth:`from_result`.
    """

    actividad_id: str
    year: int
    valuation_method: str
    closing_stock: str
    cogs: str
    bucket_event_ids: list[str] = []

    @classmethod
    def from_result(cls, result: _AppInventoryValuationPreviewResult) -> InventoryValuationPreviewPayload:
        """Flatten the application preview wrapper into this CLI :class:`InventoryValuationPreviewPayload` envelope.

        The wrapper carries an inner ``preview`` plus ``bucket_event_ids``;
        ``model_dump(mode="json")`` on the inner preview performs the
        enum/Decimal coercion, and the event ids are lifted onto the same level.
        """
        data = result.preview.model_dump(mode="json")
        data["bucket_event_ids"] = list(result.bucket_event_ids)
        return cls.model_validate(data)


# ---------------------------------------------------------------------------
# P08 — Purchase-invoice evidence sub-app
# ---------------------------------------------------------------------------


class EvidenceRecordPayload(OutputSchema):
    """One purchase-invoice evidence record.

    Mirrors ``PurchaseInvoiceEvidence.model_dump(mode='json')`` plus the
    ``bucket_event_ids`` field the CLI appends at the emit site (defaults
    to empty for read verbs).
    """

    evidence_id: str
    bucket_id: str
    source_path: str
    source_sha256: str
    media_kind: str
    supplier: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    taxable_base: str | None = None
    iva_rate: str | None = None
    iva_amount: str | None = None
    notes: str = ""
    created_at: str
    updated_at: str
    bucket_event_ids: list[str] = []


@register_schema("ledger.evidence.add")
class EvidenceAddResult(EvidenceRecordPayload):
    """JSON envelope for ``aeat app ledger evidence add``."""


@register_schema("ledger.evidence.view")
class EvidenceViewResult(EvidenceRecordPayload):
    """JSON envelope for ``aeat app ledger evidence view``."""


@register_schema("ledger.evidence.update")
class EvidenceUpdateResult(EvidenceRecordPayload):
    """JSON envelope for ``aeat app ledger evidence update``."""


@register_schema("ledger.evidence.remove")
class EvidenceRemoveResult(EvidenceRecordPayload):
    """JSON envelope for ``aeat app ledger evidence remove``."""


@register_schema("ledger.evidence.list")
class EvidenceListResult(OutputSchema):
    """JSON envelope for ``aeat app ledger evidence list``."""

    bucket_id: str
    count: int
    rows: list[dict[str, object]]


# ---------------------------------------------------------------------------
# P09 — Classification-rule sub-app
# ---------------------------------------------------------------------------


class ClassificationRulePayload(OutputSchema):
    """One classification-rule row (matches the dict emitted by rule.add / rule.list)."""

    rule_id: str
    description_pattern: str
    classification: str
    category_id: str | None = None
    priority: int
    actor: str
    created_at: str


@register_schema("ledger.rule.add")
class RuleAddResult(ClassificationRulePayload):
    """JSON envelope for ``aeat app ledger rule add``."""


@register_schema("ledger.rule.list")
class RuleListResult(OutputSchema):
    """JSON envelope for ``aeat app ledger rule list``."""

    rules: list[ClassificationRulePayload]


class RuleApplyMatchPayload(OutputSchema):
    """One dry-run match row for ``rule apply --dry-run``."""

    transaction_id: str
    description: str
    matched_rule_id: str
    classification: str


@register_schema("ledger.rule.apply")
class RuleApplyResult(OutputSchema):
    """JSON envelope for ``aeat app ledger rule apply``.

    Covers both the dry-run branch (``dry_run``, ``would_match``,
    ``count``) and the live-apply branch (``rules_evaluated``,
    ``transactions_scanned``, ``matched``, ``skipped_already_classified``,
    ``no_match``, ``applied``). All fields are optional so both branches
    validate cleanly.
    """

    # Dry-run path
    dry_run: bool | None = None
    would_match: list[RuleApplyMatchPayload] | None = None
    count: int | None = None
    # Live-apply path
    rules_evaluated: int | None = None
    transactions_scanned: int | None = None
    matched: int | None = None
    skipped_already_classified: int | None = None
    no_match: int | None = None
    applied: list[dict[str, object]] | None = None


class LLMProviderAvailabilityPayload(OutputSchema):
    """One subprocess LLM provider's PATH availability (nested)."""

    provider: str
    cli_binary: str
    available: bool
    resolved_path: str | None = None


@register_schema("ledger.providers")
class LedgerProvidersResult(OutputSchema):
    """JSON envelope for ``aeat app ledger providers``."""

    providers: list[LLMProviderAvailabilityPayload]
