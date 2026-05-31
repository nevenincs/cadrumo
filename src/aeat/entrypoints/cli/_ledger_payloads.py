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

from ._schemas import OutputSchema, register_schema

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


@register_schema("ledger.allocate")
class LedgerAllocateResult(_LedgerMutationResult):
    """JSON envelope for ``aeat app ledger allocate``."""


@register_schema("ledger.attach")
class LedgerAttachResult(_LedgerMutationResult):
    """JSON envelope for ``aeat app ledger attach``."""


@register_schema("ledger.archive")
class LedgerArchiveResult(_LedgerMutationResult):
    """JSON envelope for ``aeat app ledger archive``."""


@register_schema("ledger.stash")
class LedgerStashResult(_LedgerMutationResult):
    """JSON envelope for ``aeat app ledger stash``."""


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
    """JSON envelope for ``aeat app ledger split``."""

    bucket_id: str
    parent_transaction_id: str
    split_group_id: str
    child_transaction_ids: list[str]
    bucket_event_id: str


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
    """JSON envelope for ``aeat app ledger list``."""

    bucket_id: str
    rows: list[dict]


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
    total_count: int
    active_count: int
    archived_count: int
    stashed_count: int
    split_count: int = 0
    pending_review_count: int
    reviewed_count: int
    skipped_count: int
    period: str | None = None
    checked_transaction_count: int = 0
    readiness_issue_count: int = 0
    ready: bool | None = None


@register_schema("ledger.history")
class LedgerHistoryResult(OutputSchema):
    """JSON envelope for ``aeat app ledger history``."""

    bucket_id: str
    transaction_id: str
    event_count: int
    events: list[dict]


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
class LedgerExportResult(OutputSchema):
    """JSON envelope for ``aeat app ledger export``.

    Mirrors ``LedgerExportResult.model_dump(mode='json', exclude={'payload'})``
    plus the ``output_path`` string appended at the emit site.
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
    rows: list[dict]
    bucket_event_ids: list[str] = []
    output_path: str


@register_schema("ledger.import")
class LedgerImportResult(OutputSchema):
    """JSON envelope for ``aeat app ledger import``.

    Mirrors ``LedgerSourceImportResult.model_dump(mode='json')`` with
    the optional notice fields appended by the emit site.
    """

    rows: int
    imported: int
    skipped: int
    likely_duplicates: int = 0
    dry_run: bool
    verify: bool
    period: str | None = None
    bucket_id: str | None = None
    import_batch_id: str | None = None
    bucket_event_ids: list[str] = []
    imported_transaction_refs: list[dict] = []
    skipped_transaction_refs: list[dict] = []
    likely_duplicate_transaction_refs: list[dict] = []
    validation: LedgerImportValidationPayload
    source: LedgerImportSourcePayload
    diagnostics: list[LedgerImportDiagnosticPayload] = []
    # Optional notice fields appended at the emit site
    dry_run_notice: str | None = None
    empty_import_notice: str | None = None
    likely_duplicate_notice: str | None = None


@register_schema("ledger.track")
class LedgerTrackResult(OutputSchema):
    """JSON envelope for ``aeat app ledger track``."""

    bucket_id: str
    transaction: TransactionPayload
    tracking: dict


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
