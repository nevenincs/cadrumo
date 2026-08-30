"""Typed ``--json`` payload schemas for ledger CLI commands.

Each class declared here is a strict
:class:`OutputSchema` subclass and is referenced as a deferred public schema
target by production-authored CommandSpec so the
JSON-contract test suite can enumerate every ledger-command surface this module
covers.  Emission wraps the validated result in
:class:`SchemaEnvelope` through
:func:`emit_envelope`.

Field sets match the production payload dicts constructed in ``_ledger.py``
at their emit sites. Optional fields cover multi-branch payload shapes
(e.g. ledger.classify has a bulk path and a single-transaction path;
ledger.import carries import facts while advisories use the shared notices channel).

All sequence fields use ``list`` rather than ``tuple`` because
``model_dump(mode='json')`` serialises pydantic tuples as JSON arrays, and
the strict ``OutputSchema`` base does not coerce lists to tuples on
re-validation.

The application layer remains authoritative for
:class:`LedgerSourceImportResult`,
:class:`LedgerTransactionPayload`,
:class:`LedgerTransactionResultPayload`,
:class:`LedgerPreflightReport`.  Adjacent
surfaces that split out of this module keep their own transport schemas in
:mod:`_ledger_rule_payloads`,
:mod:`_ledger_llm_payloads`,
:mod:`_ledger_catalogue_invoice_payloads`, and
:mod:`_ledger_business_payloads` (the invoice / inventory / evidence
sub-app payload families).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field, NonNegativeInt, field_validator, model_validator

from ...application.ledger.models import (
    CurrencyCode,
    DiagnosticKind,
    DiagnosticMessage,
    DiagnosticSeverity,
    IsoDateText,
)
from ...core import LinkInconsistencyDirection, Period
from ...core.decimal import try_parse_canonical_decimal
from ...core.identity import (
    BucketId,
    CalculationRevisionId,
    FilingRecordId,
    InvoiceId,
    SnapshotId,
    TransactionId,
    WorkUnitId,
)
from ...core.json_contract import OutputRootSchema, OutputSchema
from ...core.parsing import parse_iso8601_date
from ...core.text_bounds import NonEmptyStr
from ._ledger_business_payloads import (
    AttachmentReviewPayload,
    AttachmentReviewQueueResult,
    AttachmentReviewViewResult,
    EvidenceAddResult,
    EvidenceConfirmResult,
    EvidenceExtractResult,
    EvidenceListResult,
    EvidenceRecordPayload,
    EvidenceRemoveResult,
    EvidenceUpdateResult,
    EvidenceViewResult,
    InventoryClosingAuthorityRecordResult,
    InventoryCreateResult,
    InventoryLedgerPayload,
    InventoryListResult,
    InventoryListRowPayload,
    InventoryMovementAddResult,
    InventoryMovementPayload,
    InventoryStockLayerPayload,
    InventoryValuationPreviewPayload,
)
from ._ledger_ratios_payloads import (
    RatiosEligibleResult,
    RatiosEligibleRowPayload,
    RatiosListResult,
    RatiosRowPayload,
    RatiosSetResult,
    RatiosUnsetResult,
    RatiosValidateFindingPayload,
    RatiosValidateResult,
)
from ._ledger_rule_payloads import (
    ClassificationRulePayload,
    RuleAddResult,
    RuleApplyAppliedPayload,
    RuleApplyMatchPayload,
    RuleApplyResult,
    RuleListResult,
)

_LEDGER_BUSINESS_PAYLOAD_EXPORTS = (
    AttachmentReviewPayload,
    AttachmentReviewQueueResult,
    AttachmentReviewViewResult,
    EvidenceAddResult,
    EvidenceConfirmResult,
    EvidenceExtractResult,
    EvidenceListResult,
    EvidenceRecordPayload,
    EvidenceRemoveResult,
    EvidenceUpdateResult,
    EvidenceViewResult,
    InventoryCreateResult,
    InventoryClosingAuthorityRecordResult,
    InventoryLedgerPayload,
    InventoryListResult,
    InventoryListRowPayload,
    InventoryMovementAddResult,
    InventoryMovementPayload,
    InventoryStockLayerPayload,
    InventoryValuationPreviewPayload,
)
_LEDGER_RULE_PAYLOAD_EXPORTS = (
    ClassificationRulePayload,
    RuleAddResult,
    RuleApplyAppliedPayload,
    RuleApplyMatchPayload,
    RuleApplyResult,
    RuleListResult,
)
_LEDGER_RATIOS_PAYLOAD_EXPORTS = (
    RatiosEligibleResult,
    RatiosEligibleRowPayload,
    RatiosListResult,
    RatiosRowPayload,
    RatiosSetResult,
    RatiosUnsetResult,
    RatiosValidateFindingPayload,
    RatiosValidateResult,
)

if TYPE_CHECKING:
    from ...application.ledger.models import LedgerExportResult as _AppLedgerExportResult
    from ...application.ledger.models import LedgerSourceImportResult as _AppLedgerSourceImportResult

# ---------------------------------------------------------------------------
# Shared nested models (not direct CommandSpec schema targets)
# ---------------------------------------------------------------------------


class M210IncomeClassificationPayload(OutputSchema):
    """Operator-visible persisted M210 classification facts for one ledger row."""

    official_tipo_renta_code: str
    gross_income_amount: str
    applicable_rate: str
    payer_mode: str
    payer_id: str | None = None
    asset_or_right_id: str | None = None


class TransactionPayload(OutputSchema):
    """Nested CLI copy of :class:`LedgerTransactionPayload`.

    Field constraints mirror the canonical projection so a malformed
    identity, date, currency, or blank description that
    ``LedgerTransactionPayload`` refuses is refused at the CLI boundary too.
    """

    transaction_id: TransactionId
    date: IsoDateText
    booked_date: IsoDateText
    value_date: str | None = None
    amount: NonEmptyStr
    currency: CurrencyCode
    direction: NonEmptyStr
    counterparty: str = ""
    description: NonEmptyStr
    business_classification: NonEmptyStr
    business_pct: str | None = None
    category_id: str | None = None
    taxable_base: str | None = None
    iva_rate: str | None = None
    iva_amount: str | None = None
    iva_category: str | None = None
    counterparty_country: str | None = None
    counterparty_identification_state: str | None = None
    irpf_category: str | None = None
    m210_income_classification: M210IncomeClassificationPayload | None = None
    usage_ratio_id: str | None = None
    prorrata_reference: str | None = None
    purchase_invoice_evidence_id: str | None = None
    attachment_ids: list[str] = []
    notes: str = ""
    lifecycle_state: NonEmptyStr
    classified_by: NonEmptyStr
    # Decision-provenance fields: the "why" behind the active
    # classification decision. Declared here so the strict single-transaction
    # read surface (ledger view/classify/update/archive/stash) accepts the
    # persisted provenance fields rather than rejecting them as
    # extra_forbidden.
    classified_at: str | None = None
    classification_reason: str = ""
    classification_confidence: str | None = None
    source_jurisdiction: str | None = None
    # FX provenance for foreign-currency rows: the
    # EUR-equivalent and applied CCY->EUR rate the application payload emits.
    # Declared here so the strict single-transaction read surface (ledger
    # view/classify/update/archive/stash) accepts the persisted FX fields
    # rather than rejecting them as extra_forbidden. None for EUR-native rows.
    value_in_eur: str | None = None
    fx_rate: str | None = None
    # Persistence-record lifecycle timestamps, rendered as ISO-8601 strings.
    created_at: str
    modified_at: str


class BulkClassifyFailurePayload(OutputSchema):
    """One failed row from a bulk classify operation."""

    row_index: int
    transaction_id: str
    reason: str


class SpendingCategoryFamilyPayload(OutputSchema):
    """One spending category family entry in the categories catalogue."""

    family: str
    category_ids: list[str]


class LedgerIrpfCategoryPayload(OutputSchema):
    """One ``--irpf-category`` value exposed by ``ledger categories``."""

    id: str
    purpose: str
    directions: list[str]
    net_paid_invoice: bool
    related_category_ids: list[str]


class LedgerReviewRowPayload(OutputSchema):
    """One :class:`LedgerReviewRow` transport row.

    Mirrors the canonical row's constraints rather than restating its fields as
    free strings: the id is the content-addressed transaction identity, the
    date is the 10-character ISO day, and the amount, description and review
    status are the values the row was projected from. Declared as bare ``str``
    this transport accepted ``id='bad'``, ``date='bad'`` and blank
    amount/description that :class:`LedgerReviewRow` itself refuses.
    """

    id: TransactionId
    date: IsoDateText
    amount: NonEmptyStr
    description: NonEmptyStr
    status: NonEmptyStr
    transaction: TransactionPayload | None = None


class LedgerRemovalBlockerPayload(OutputSchema):
    """One modelo revision reference surfaced by ledger removal.

    Mirrors :class:`LedgerRemovalBlocker`.  In
    ``blocking_modelo_references`` the row names a finalized revision that
    prevents removal because it still cites the transaction through
    ``source_transaction_ids``.  In ``stale_draft_revision_references`` the same
    shape is a non-blocking draft advisory that tells the operator which
    borradores should be recalculated after removal.
    """

    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    revision_state: str
    modelo: str
    filing_year: int
    period: str


class LedgerPeriodPayload(OutputSchema):
    """Nested filing-period projection used by ledger readiness surfaces.

    Carries the JSON-safe filing year plus period code derived from
    :class:`Period`; preflight/check reports use this shape instead
    of serialising the richer period object directly.
    """

    filing_year: int
    code: str


class LedgerTransactionParticipationEntryPayload(OutputSchema):
    """One finalized-revision participation recorded against a ledger transaction.

    Surfaces the inverse of the forward ``source_transaction_ids`` link:
    a finalized modelo revision (and, where filed, its filing record and
    justificante reference) that consumed the transaction.  The row mirrors
    :class:`TransactionRevisionParticipation`, which lives
    in the derived, rebuildable participation index rather than on the
    content-addressed transaction itself.
    """

    calculation_revision_id: CalculationRevisionId
    work_unit_id: WorkUnitId
    modelo: str
    filing_year: int
    period: Period
    revision_state: str
    filing_record_id: FilingRecordId | None = None
    justificante_reference: str | None = None


class LedgerImportTransactionRefPayload(OutputSchema):
    """One bucket-qualified transaction reference nested in the import result.

    Mirrors :class:`BucketTransactionRef`'s
    ``model_dump(mode="json")`` — replaces the former bare ``dict[str, object]``
    on the imported / skipped / likely-duplicate ref lists.
    """

    bucket_id: BucketId
    transaction_id: TransactionId


class LedgerImportValidationPayload(OutputSchema):
    """Source-file validation details from :class:`LedgerSourceValidationReport`."""

    valid: bool
    warnings: list[str] = []
    encoding: str | None = None
    dialect: str | None = None


class LedgerImportSourcePayload(OutputSchema):
    """Source-file verification details from :class:`LedgerSourceVerificationReport`."""

    requested: bool
    path: str | None = None
    sha256: str | None = None


class LedgerImportDiagnosticPayload(OutputSchema):
    """One :class:`LedgerImportDiagnosticReport` entry."""

    kind: DiagnosticKind
    severity: DiagnosticSeverity
    message: DiagnosticMessage
    source_path: str | None = None
    source_locator: str | None = None
    affected_transaction_ids: list[str] = []


class LedgerSplitChildIdPayload(OutputSchema):
    """One persisted split-child id, carrying both the full and short forms.

    Emitted on the manual / applied split surface so an operator can copy the
    ids straight into ``aeat app ledger merge --child-id ...`` to undo the split.
    ``full_id`` is the 64-char canonical id ``merge`` resolves; ``display_id`` is
    the shortest unique prefix within the child cohort (the same display-width
    convention :class:`LedgerListRowPayload` uses), suitable for human reading.
    """

    full_id: str
    display_id: str


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
# Mutation verb result schemas
# ---------------------------------------------------------------------------


class _LedgerMutationResult(OutputSchema):
    """Shared shape for single-transaction mutation verbs.

    The uniform mutation quintet: every verb that mutates exactly one ledger
    transaction returns ``{bucket_id, transaction_id, bucket_event_ids,
    review_status, transaction}``. Subclassed per verb so each CommandSpec can
    reference its own schema target.
    """

    bucket_id: BucketId
    transaction_id: TransactionId
    bucket_event_ids: list[str]
    review_status: str
    transaction: TransactionPayload


class LedgerAddResult(_LedgerMutationResult):
    """JSON envelope for ``aeat app ledger add``.

    ``add`` joins the uniform mutation quintet by subclassing
    :class:`_LedgerMutationResult`, gaining the ``review_status`` field every
    other single-transaction mutation already carries.
    """


class LedgerUpdateResult(_LedgerMutationResult):
    """JSON envelope for ``aeat app ledger update``."""


class LedgerClassifySingleResult(_LedgerMutationResult):
    """JSON envelope for the single-transaction ``aeat app ledger classify`` path.

    The primary, non-optional mutation quintet: classifying one transaction
    returns the same ``{bucket_id, transaction_id, bucket_event_ids,
    review_status, transaction}`` shape every other single-transaction
    mutation carries, rather than the former all-optional union.
    """


class LedgerClassifyBulkResult(OutputSchema):
    """JSON result for the bulk ``aeat app ledger classify --file`` path.

    Structurally distinct from :class:`LedgerClassifySingleResult`: a bulk run
    reports row counts across many transactions, not one mutation quintet.
    """

    total: int
    applied: int
    skipped: int
    failures: list[BulkClassifyFailurePayload] = []


class LedgerClassifyResult(OutputRootSchema[LedgerClassifySingleResult | LedgerClassifyBulkResult]):
    """JSON envelope for ``aeat app ledger classify``, either branch.

    The one CLI leaf emits two structurally distinct shapes depending on
    ``--file``: the single-transaction mutation quintet
    (:class:`LedgerClassifySingleResult`) or the bulk row-count summary
    (:class:`LedgerClassifyBulkResult`). The JSON-schema conformance gate maps
    exactly one graph-declared schema per CLI leaf, so this discriminated root
    validates either branch under the one ``ledger.classify`` command key;
    ``model_dump`` serialises the flat branch shape, not a wrapped root.
    """


class LedgerAllocateResult(_LedgerMutationResult):
    """JSON envelope for ``aeat app ledger allocate``."""


class LedgerAttachResult(_LedgerMutationResult):
    """JSON envelope for ``aeat app ledger attach`` and ``ledger doclink``."""


class LedgerDetachResult(_LedgerMutationResult):
    """JSON envelope for ``aeat app ledger detach``.

    The same uniform single-transaction mutation shape the attach side returns:
    detaching is a mutation of one addressable transaction, so it reports the
    quintet rather than a bespoke payload.
    """


class LedgerEvidencePullAllFilePayload(OutputSchema):
    """One Drive folder child's fetch outcome from ``ledger evidence pull-all``.

    ``fetched`` is ``True`` when the file's bytes were fetched and encrypted
    into the attachment store (``attachment_id`` set); ``False`` when the
    fetch was refused (``refusal_reason`` set) — a Drive file outside the
    ``drive.file`` scope never becomes a link-only evidence row.
    """

    file_id: str
    name: str
    mime_type: str
    fetched: bool
    attachment_id: str | None = None
    refusal_reason: str | None = None


class LedgerEvidencePullAllResult(OutputSchema):
    """JSON envelope for ``aeat app ledger evidence pull-all``.

    Bulk-fetches every PDF/image child of a ``drive.file``-reachable Drive
    folder into encrypted attachment evidence (never a link-only pointer),
    reporting one :class:`LedgerEvidencePullAllFilePayload` row per child.
    Gmail bulk fetch is out of scope pending a separate ``gmail.readonly``
    scope-upgrade decision.
    """

    bucket_id: BucketId
    folder_id: str
    total_documents: int
    fetched_count: int
    refused_count: int
    skipped_non_document_count: int
    files: list[LedgerEvidencePullAllFilePayload] = []


class LedgerArchiveResult(_LedgerMutationResult):
    """JSON envelope for ``aeat app ledger archive``."""


class LedgerStashResult(_LedgerMutationResult):
    """JSON envelope for ``aeat app ledger stash``."""


class LedgerRestoreResult(_LedgerMutationResult):
    """JSON envelope for ``aeat app ledger restore``."""


class LedgerExcludeResult(_LedgerMutationResult):
    """JSON envelope for ``aeat app ledger exclude``.

    Marks a reviewed transaction as deliberately excluded from filing; the
    ``review_status`` field carries ``excluded`` and the row stays in the
    uniform mutation quintet.
    """


class LedgerRemoveResult(OutputSchema):
    """JSON envelope for ``aeat app ledger remove``.

    Mirrors :class:`LedgerTransactionRemovalReport`.
    ``blocking_modelo_references`` is the hard finalized-revision guard;
    ``stale_draft_revision_references`` is advisory evidence for borradores that
    still cite the removed transaction and should be recalculated.
    """

    bucket_id: BucketId
    transaction_id: TransactionId
    removed: bool = False
    dry_run: bool = False
    actor: str
    reason: str = ""
    cascaded_purchase_invoice_evidence_ids: list[str] = []
    cascaded_attachment_ids: list[str] = []
    blocking_modelo_references: list[LedgerRemovalBlockerPayload] = []
    stale_draft_revision_references: list[LedgerRemovalBlockerPayload] = []
    bucket_event_ids: list[str] = []


class LedgerResetResult(OutputSchema):
    """JSON envelope for ``aeat app ledger reset``.

    Mirrors ``LedgerCatalogueResetReport.model_dump(mode='json')``.
    """

    bucket_id: BucketId
    removed_transaction_ids: list[str] = []
    reset: bool = False
    dry_run: bool = False
    actor: str
    reason: str = ""
    cascaded_purchase_invoice_evidence_ids: list[str] = []
    cascaded_attachment_ids: list[str] = []
    blocking_modelo_references: list[LedgerRemovalBlockerPayload] = []
    stale_draft_revision_references: list[LedgerRemovalBlockerPayload] = []
    bucket_event_ids: list[str] = []


class LedgerSplitResult(OutputSchema):
    """JSON envelope for ``aeat app ledger split``.

    Covers the manual split (explicit ``--child-amount`` / ``--child-description``)
    and the evidence-driven LLM split (``--llm``). On the LLM preview path
    (``--llm`` without ``--apply``) ``persisted`` is False, nothing is written, and
    ``proposed_children`` carries the derived child amounts for review; the
    structural ``split_group_id`` / ``bucket_event_id`` appear only once a split is
    actually persisted.
    """

    bucket_id: BucketId
    parent_transaction_id: TransactionId
    split_group_id: str | None = None
    child_transaction_ids: list[str] = []
    # Persisted child ids in full + short form so the operator can copy them
    # into ``ledger merge --child-id`` to undo the split (audit M11). Empty on
    # the LLM preview path, where nothing is persisted yet.
    child_transactions: list[LedgerSplitChildIdPayload] = []
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


class LedgerMergeResult(OutputSchema):
    """JSON envelope for ``aeat app ledger merge``."""

    bucket_id: BucketId
    split_group_id: str
    parent_transaction_id: TransactionId
    merged_transaction_id: TransactionId
    source_child_ids: list[str]
    bucket_event_id: str


# ---------------------------------------------------------------------------
# Query verb result schemas
# ---------------------------------------------------------------------------


class LedgerListRowPayload(OutputSchema):
    """One typed ``aeat app ledger list`` row.

    Projected from
    :class:`LedgerTransactionReviewPayload` plus the
    three id/group keys the list builder appends (``full_id``,
    ``display_id``, ``group_label``). Carries the non-negative ``amount`` magnitude
    plus ``direction`` and the ``created_at`` /
    ``modified_at`` lifecycle timestamps.
    """

    # Identity / display
    full_id: str
    display_id: str
    transaction_id: TransactionId
    # Core read projection (mirrors LedgerTransactionReviewPayload)
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
    iva_category: str | None = None
    counterparty_country: str | None = None
    counterparty_identification_state: str | None = None
    irpf_category: str | None = None
    m210_income_classification: M210IncomeClassificationPayload | None = None
    usage_ratio_id: str | None = None
    prorrata_reference: str | None = None
    purchase_invoice_evidence_id: str | None = None
    attachment_ids: list[str] = []
    notes: str = ""
    lifecycle_state: str
    review_status: str
    classified_by: str
    # Decision-provenance fields: present so the row validates from
    # the shared `LedgerTransactionReviewPayload` dump without rejecting
    # extra keys; not rendered in the tab-delimited list line (view/history
    # are the dedicated provenance surfaces).
    classified_at: str | None = None
    classification_reason: str = ""
    classification_confidence: str | None = None
    source_jurisdiction: str | None = None
    value_in_eur: str | None = None
    fx_rate: str | None = None
    created_at: str
    modified_at: str
    # List-builder extras
    group_label: str | None = None


class LedgerListResult(OutputSchema):
    """JSON envelope for ``aeat app ledger list``.

    ``rows`` is the page actually rendered; ``total`` is the full bucket row
    count. When ``--limit`` clips the page, ``truncated`` is ``True`` and
    ``offset`` / ``limit`` describe the window so a large ledger is never
    silently capped — the consumer can always see that more rows exist.
    """

    bucket_id: BucketId
    rows: list[LedgerListRowPayload]
    total: int = 0
    shown: int = 0
    offset: int = 0
    limit: int | None = None
    truncated: bool = False


class LedgerViewResult(OutputSchema):
    """JSON envelope for ``aeat app ledger view``.

    Mirrors ``LedgerTransactionResultPayload``.
    """

    bucket_id: BucketId
    transaction_id: TransactionId
    review_status: str
    transaction: TransactionPayload


class LedgerStatusResult(OutputSchema):
    """JSON envelope for ``aeat app ledger status``.

    Mirrors :class:`LedgerStatusReport`.  With no
    period it is an at-a-glance bucket summary; with ``--period`` it adds the
    ledger preflight counts and readiness verdict for the selected
    :class:`Period`.  The money totals are gross EUR roll-ups over
    active business/mixed rows, not modelo registry calculations.
    """

    bucket_id: BucketId
    business_income_total: str = "0.00"
    business_expense_total: str = "0.00"
    business_net_total: str = "0.00"
    total_count: NonNegativeInt
    active_count: NonNegativeInt
    archived_count: NonNegativeInt
    stashed_count: NonNegativeInt
    split_count: NonNegativeInt = 0
    pending_review_count: NonNegativeInt
    reviewed_count: NonNegativeInt
    skipped_count: NonNegativeInt
    period: Period | None = None
    checked_transaction_count: NonNegativeInt = 0
    readiness_issue_count: NonNegativeInt = 0
    ready: bool | None = None


class LedgerHistoryEventPayload(OutputSchema):
    """One bucket event nested in ``aeat app ledger history``.

    Mirrors :class:`BucketEvent`'s
    ``model_dump(mode="json")`` — replaces the former bare ``dict[str, object]`` event shape. The
    ``payload`` mapping stays a typed ``dict[str, str]`` (the append-only event's
    free-form short-string detail, per the bucket-event contract), not a bare
    ``object`` map.
    """

    event_id: str
    bucket_id: BucketId
    event_type: str
    occurred_at: str
    actor: str
    object_type: str
    object_id: str
    payload_version: int
    payload: dict[str, str] = {}


class LedgerHistoryResult(OutputSchema):
    """JSON envelope for ``aeat app ledger history``."""

    bucket_id: BucketId
    transaction_id: TransactionId
    event_count: int
    events: list[LedgerHistoryEventPayload]


class LedgerCategoriesResult(OutputSchema):
    """JSON envelope for ``aeat app ledger categories``."""

    families: list[SpendingCategoryFamilyPayload]
    category_ids: list[str]
    irpf_categories: list[LedgerIrpfCategoryPayload]
    irpf_category_ids: list[str]
    net_paid_withholding_irpf_category_ids: list[str]
    income_requires_category: bool


# ---------------------------------------------------------------------------
# Import / export / track / review verb result schemas
# ---------------------------------------------------------------------------


class LedgerExportRowPayload(OutputSchema):
    """One serialised ledger row nested in ``aeat app ledger export``.

    Mirrors :class:`LedgerExportRow`'s
    ``model_dump(mode="json")``. The flow stays the non-negative ``amount``
    magnitude plus the ``direction`` authority; every other column is
    a string the serializer already emits ("" for an absent optional column).
    """

    bucket_id: BucketId
    transaction_id: TransactionId
    lifecycle_state: str
    booked_date: IsoDateText
    value_date: str = ""
    effective_date: IsoDateText
    amount: NonEmptyStr
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    direction: str
    counterparty: str = ""
    description: str
    business_classification: str
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
    value_in_eur: str = ""
    fx_rate: str = ""

    @field_validator("booked_date", "effective_date")
    @classmethod
    def _require_iso_date(cls, value: str) -> str:
        """Keep exported mandatory dates parseable without changing their JSON wire form."""
        if parse_iso8601_date(value) is None:
            raise ValueError("must be an ISO-8601 date")
        return value

    @field_validator("value_date")
    @classmethod
    def _validate_optional_iso_date(cls, value: str) -> str:
        if value:
            cls._require_iso_date(value)
        return value

    @field_validator("amount", "taxable_base", "iva_amount", "value_in_eur")
    @classmethod
    def _require_non_negative_decimal(cls, value: str) -> str:
        if not value:
            return value
        parsed = try_parse_canonical_decimal(value)
        if parsed is None:
            raise ValueError("must be a canonical decimal")
        if parsed < 0:
            raise ValueError("must be a non-negative decimal")
        return value


class LedgerExportPayload(OutputSchema):
    """JSON envelope for ``aeat app ledger export``.

    Distinct from the application
    :class:`LedgerExportResult`: the backend
    result carries the raw ``payload`` bytes and typed members (``BucketId``,
    ``ExportSerializationFormat``, ``LedgerExportRow``); this
    envelope projects the JSON-coerced metadata + row view and appends the
    operator-facing ``output_path``. Derive instances via
    :meth:`LedgerExportPayload.from_result`.
    """

    bucket_id: BucketId
    export_id: SnapshotId
    export_format: str
    media_type: str
    filename_extension: str
    row_count: NonNegativeInt
    byte_size: NonNegativeInt
    sha256: SnapshotId
    fieldnames: list[str]
    rows: list[LedgerExportRowPayload]
    bucket_event_ids: list[str] = []
    output_path: str

    @classmethod
    def from_result(cls, result: _AppLedgerExportResult, *, output_path: str) -> LedgerExportPayload:
        """Project the application export result into this CLI envelope.

        The raw ``payload`` bytes are excluded — the JSON envelope carries
        export metadata and the row projection, not the binary artefact (that
        is written to ``output_path``). ``model_dump(mode="json")`` performs the
        typed-id/enum/nested-row coercion so the envelope's loosened field types
        stay exactly consistent with the backend contract.

        Returns:
            :class:`LedgerExportPayload` ready for the CLI JSON envelope.
        """
        data = result.model_dump(mode="json", exclude={"payload"})
        data["output_path"] = output_path
        return cls.model_validate(data)


class LedgerImportPayload(OutputSchema):
    """JSON envelope for ``aeat app ledger import``.

    Distinct from the application
    :class:`LedgerSourceImportResult`: this
    envelope projects that result's JSON-coerced fields; non-blocking import
    advisories use the shared envelope ``notices`` channel.
    """

    rows: NonNegativeInt
    imported: NonNegativeInt
    skipped: NonNegativeInt
    likely_duplicates: NonNegativeInt = 0
    dry_run: bool
    verify: bool
    period: Period | None = None
    bucket_id: BucketId | None = None
    import_batch_id: str | None = None
    bucket_event_ids: list[str] = []
    imported_transaction_refs: list[LedgerImportTransactionRefPayload] = []
    skipped_transaction_refs: list[LedgerImportTransactionRefPayload] = []
    likely_duplicate_transaction_refs: list[LedgerImportTransactionRefPayload] = []
    validation: LedgerImportValidationPayload
    source: LedgerImportSourcePayload
    diagnostics: list[LedgerImportDiagnosticPayload] = []

    @classmethod
    def from_result(cls, result: _AppLedgerSourceImportResult) -> LedgerImportPayload:
        """Project the application import result into this CLI envelope.

        ``model_dump(mode="json")`` coerces the typed members (typed-ids, nested
        validation/source/diagnostic reports) to the JSON shape this envelope
        declares. Advisories are intentionally excluded because the shared
        envelope notice schema is their canonical transport.

        Returns:
            :class:`LedgerImportPayload` ready for the CLI JSON envelope.
        """
        data = result.model_dump(mode="json")
        return cls.model_validate(data)


class LedgerTransactionParticipationPayload(OutputSchema):
    """JSON envelope for ``aeat app ledger participation <transaction-id>``.

    Carries the full
    :class:`TransactionRevisionParticipationIndex` read for
    one ledger transaction: every finalized modelo revision and filing that
    consumed it.  An empty ``participations`` list is the auditable "not used in
    any finalized declaration" answer, not a lookup failure.
    """

    transaction_id: TransactionId
    participations: list[LedgerTransactionParticipationEntryPayload]


class LedgerParticipationRebuildResult(OutputSchema):
    """JSON envelope for ``aeat app ledger participation rebuild``.

    Reports the outcome of
    :func:`rebuild_participation_index`, which
    regenerates the derived participation index from the authoritative finalized
    calculation-revision catalogue.  The result is a repair summary for the
    read-side cache, not a mutation of ledger transactions.

    ``stale_removed_count`` reports the participation objects pruned because the
    regenerated catalogue no longer records them; a non-zero value means the
    cache had been surfacing revisions the authoritative catalogue had dropped.
    """

    transaction_count: int
    participation_count: int
    revision_count: int
    stale_removed_count: int


class LedgerTrackingProvenancePayload(OutputSchema):
    """One evidence-link lineage entry nested in ``ledger track``.

    Mirrors
    :class:`TransactionEvidenceProvenanceEntry`'s JSON
    dump; ``linked_at`` is the ISO-8601 timestamp.
    """

    evidence_id: str
    evidence_kind: str
    actor: str
    source_command: str
    linked_at: str
    bucket_event_id: str | None = None


class LedgerTrackingEditPayload(OutputSchema):
    """One manual-correction lineage entry nested in ``ledger track``.

    Mirrors :class:`TransactionEditLineageEntry`'s
    JSON dump; ``edited_at`` is the ISO-8601 timestamp.
    """

    previous_transaction_id: TransactionId
    actor: str
    source_command: str
    edited_at: str
    bucket_event_id: str | None = None


class LedgerTrackingLifecyclePayload(OutputSchema):
    """One lifecycle-transition lineage entry nested in ``ledger track``.

    Mirrors
    :class:`TransactionLifecycleLineageEntry`'s JSON
    dump; ``changed_at`` is the ISO-8601 timestamp.
    """

    previous_state: str
    state: str
    actor: str
    source_command: str
    changed_at: str
    reason: str = ""
    bucket_event_id: str | None = None


class LedgerTrackingPayload(OutputSchema):
    """Durable event-lineage projection for one transaction.

    Mirrors
    :class:`LedgerTransactionTrackingPayload`'s JSON
    dump — replaces the former bare ``dict[str, object]`` ``tracking`` field on
    :class:`LedgerTrackResult`.
    """

    transaction_id: TransactionId
    created_event_id: str | None = None
    evidence_provenance: list[LedgerTrackingProvenancePayload] = []
    edit_lineage: list[LedgerTrackingEditPayload] = []
    lifecycle_state: str
    lifecycle_lineage: list[LedgerTrackingLifecyclePayload] = []


class LedgerTrackResult(OutputSchema):
    """JSON envelope for ``aeat app ledger track``.

    ``participated_in`` carries the finalized-revision participations that
    consumed this transaction (the inverse audit trail), or ``None`` when the
    transaction appears in no finalized revision.  The field is read from
    :class:`TransactionRevisionParticipationIndex` and
    complements the transaction's own evidence/edit/lifecycle lineage.
    """

    bucket_id: BucketId
    transaction: TransactionPayload
    tracking: LedgerTrackingPayload
    participated_in: list[LedgerTransactionParticipationEntryPayload] | None = None


class LedgerReviewResult(OutputSchema):
    """JSON envelope for ``aeat app ledger review``.

    Covers three payload branches:
    - Multi-row list: ``rows`` + ``filters``
    - Empty-result (positional id with no match): empty ``rows`` + ``filters``
    - Single-row detail: scalar fields for the matched row

    Every field is optional because the branches are disjoint, so the branch
    invariant below -- not the field types -- is what makes the envelope
    honest: without it ``model_validate({})``, ``{"filters": []}`` and a
    half-populated detail all validated, and an operator could not tell an
    empty result from a malformed one.

    The detail fields carry the same constraints as
    :class:`LedgerReviewRowPayload`, so a detail branch cannot claim a row
    shape the canonical projection would refuse.
    """

    # Multi-row and empty-result paths
    rows: list[LedgerReviewRowPayload] | None = None
    filters: list[str] | None = None
    # Single-transaction detail path
    id: TransactionId | None = None
    date: IsoDateText | None = None
    amount: NonEmptyStr | None = None
    description: NonEmptyStr | None = None
    review_status: NonEmptyStr | None = None
    transaction: TransactionPayload | None = None
    verbose: bool | None = None

    @model_validator(mode="after")
    def _exactly_one_complete_branch(self) -> LedgerReviewResult:
        """Require the envelope to be exactly one of the three documented branches.

        ``rows``/``filters`` together are the list branch (an empty ``rows`` is
        the legitimate no-match result); the five detail fields together are the
        detail branch. Mixing them, or populating neither, describes no
        outcome the command can produce.

        Raises:
            ValueError: The envelope is neither a complete list branch nor a
                complete detail branch, or is both.
        """
        detail_fields = (self.id, self.date, self.amount, self.description, self.review_status)
        is_list_branch = self.rows is not None and self.filters is not None
        detail_present = sum(field is not None for field in detail_fields)
        is_detail_branch = detail_present == len(detail_fields)
        if is_list_branch and detail_present:
            raise ValueError("ledger review result must not mix the list and detail branches")
        if not is_list_branch and not is_detail_branch:
            raise ValueError(
                "ledger review result must populate either rows and filters, "
                "or every one of id, date, amount, description and review_status",
            )
        return self


# ---------------------------------------------------------------------------
# Diagnostic verb result schemas (check / preflight / link)
# ---------------------------------------------------------------------------


class LedgerPreflightIssuePayload(OutputSchema):
    """One readiness issue attached to a ledger transaction.

    Mirrors :class:`LedgerPreflightIssue`: the
    transaction id, machine-readable reason, and operator detail explaining which
    fact blocks or warns before modelo calculation.
    """

    transaction_id: TransactionId
    reason: str
    detail: str = Field(min_length=1, max_length=512)


class LedgerLinkInconsistencyPayload(OutputSchema):
    """One one-sided invoice/transaction link found by the check verb.

    Mirrors :class:`~cadrumo.domain.invoices.LinkInconsistency`. ``direction``
    names which catalogue cites the other without being cited back:
    ``invoice-only`` when the invoice carries the transaction in its
    ``linked_transaction_ids`` but the transaction's ``invoice_id`` does not
    point back, ``transaction-only`` for the reverse. Either way the two
    catalogues disagree about a link and the association cannot be trusted
    until the operator re-runs ``link``.

    ``direction`` stays typed as the core
    :class:`~cadrumo.core.LinkInconsistencyDirection` all the way to the
    operator boundary, so the closed value set is validated here rather than
    degrading to a free-form string on the way out.
    """

    invoice_id: str
    transaction_id: TransactionId
    direction: LinkInconsistencyDirection


class LedgerCheckResult(OutputSchema):
    """JSON envelope for ``aeat app ledger check``.

    ``check`` is a report-only audit over one explicit period or every period the
    ledger touches.  It aggregates
    :func:`preflight_transaction_catalogue` issue rows
    into a bucket-level readiness verdict without mutating transactions.

    ``link_inconsistencies`` is the second, period-independent channel: the
    one-sided invoice/transaction links
    :func:`~cadrumo.application.invoices.verify_invoice_repository_links`
    reports over the whole bucket. ``ready`` is false when either channel is
    non-empty, because a disagreeing link makes the affected rows' invoice
    association untrustworthy just as a missing fact does.
    """

    bucket_id: BucketId
    periods: list[str]
    checked_transaction_count: int
    issues: list[LedgerPreflightIssuePayload]
    link_inconsistencies: list[LedgerLinkInconsistencyPayload] = []
    ready: bool


class LedgerPreflightResult(OutputSchema):
    """JSON envelope for ``aeat app ledger preflight``.

    Mirrors :class:`LedgerPreflightReport` produced by
    :func:`preflight_ledger_tax_readiness`. ``period``
    is the nested
    :class:`LedgerPeriodPayload` model
    dump, ``issues`` are
    :class:`LedgerPreflightIssuePayload`
    rows, and ``ready`` is the computed no-issues verdict.
    """

    bucket_id: BucketId
    period: LedgerPeriodPayload
    checked_transaction_count: int
    issues: list[LedgerPreflightIssuePayload]
    ready: bool


class LedgerLinkResult(OutputSchema):
    """JSON envelope for ``aeat app ledger link``.

    ``link`` establishes an invoice-only bidirectional relationship and carries
    only the link metadata. Evidence assignment is a separate operation
    (``aeat app ledger attach``) and never rides on this result.
    """

    operation: str
    bucket_id: BucketId
    transaction_id: TransactionId
    invoice_id: InvoiceId
    actor: str


# ---------------------------------------------------------------------------
# Usage-ratios sub-app result schemas
# ---------------------------------------------------------------------------
