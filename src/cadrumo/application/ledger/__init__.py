"""Application facade for bucket-scoped ledger and invoice-adjacent workflows.

Owns the operator-facing ledger lifecycle: importing bank statements and
records, classifying transactions for tax, splitting and merging entries,
attaching evidence, and checking a period's tax-readiness before a modelo
calculation consumes it. The primary movement fact remains
``ledger_transaction``. Purchase invoice evidence and payable / collectible
business invoices are related bucket-scoped records, not ledger rows, and their
source-kind identity is carried by
:class:`BusinessOperationInvoiceDirection`.

The ledger-mounted invoice surface is intentionally slim:
:class:`BusinessOperationInvoice` records carry the
:class:`BusinessOperationInvoiceDirection` source-kind discriminator consumed by
:class:`PayableInvoiceService` and :class:`CollectibleInvoiceService`. Rich
invoice-line detail and reconciliation links stay in
:mod:`domain.invoices`, while the application invoice package maps issued /
received invoice directions back onto
:attr:`core.BindingSourceKind.PAYABLE_INVOICE` and
:attr:`core.BindingSourceKind.COLLECTIBLE_INVOICE`.

Major declarations:

* :func:`import_ledger_source` and
  :func:`bulk_classify_from_csv` - the
  ingest and batch-classification entry points.
* :func:`create_manual_transaction`,
  :func:`split_transaction`, and
  :func:`merge_transactions` - manual ledger edits.
* :func:`preflight_ledger_tax_readiness` with
  :class:`LedgerPreflightReport` and
  :class:`LedgerPreflightIssue` - the readiness gate
  that reports rows missing a category, usage-ratio reference, base, IVA rate,
  currency, censo-aligned HOME_OFFICE ratio, or prorrata reference.
* :func:`eligible_ratio_categories`,
  :func:`set_usage_ratio`,
  :func:`unset_usage_ratio`, and
  :func:`validate_ratios_for_bucket` - the
  operator-facing ``aeat app ledger ratios`` backend that bridges category
  proportionality rules to persisted usage-ratio overrides.
* :class:`PurchaseInvoiceEvidenceService` - the
  evidence lifecycle for receipts or supplier invoice artefacts attached to
  ledger transactions, and :func:`extract_invoice_fields` with
  :class:`InvoiceDraft` - the on-host field-extraction primitive an operator
  reviews before minting a :class:`domain.invoices.Invoice` from a PDF.
* :func:`confirm_invoice_draft_from_evidence` with
  :class:`InvoiceConfirmationResult` - the non-interactive confirm step that
  re-extracts a draft, layers operator overrides on top, and delegates the
  actual write to :func:`application.invoices.create_catalogue_invoice`.
* :class:`PayableInvoiceService`,
  :class:`CollectibleInvoiceService`, and
  :class:`BusinessOperationInvoiceRepository` - the
  encrypted CRUD surface behind ``aeat app ledger invoice --kind issued|received``.
* :func:`resolve_transaction_id` - the
  unambiguous-prefix id resolver, and
  :func:`resolve_lineage_transaction_id` - its
  read-side lineage-aware
  variant that resolves a superseded (pre-edit) handle to the live row.
* The typed command and result records
  (:class:`LedgerSourceImportCommand`,
  :class:`LedgerImportOperationResult`,
  :class:`LedgerReviewQueryResult`,
  :class:`LedgerStatusReport`, and siblings) that
  carry each operation across the CLI boundary.

See Also:
    :mod:`application.invoices`
        Rich invoice orchestration and the
        :class:`application.invoices.InvoiceCatalogueSourceResolver` that
        adapts invoice records into the calculation source mesh.
    :mod:`application.aggregation`
        Ledger aggregation resolvers such as
        :class:`application.aggregation.LedgerIvaAggregationSourceResolver`
        and the shared
        :class:`application.aggregation.CalculationSourceResolution`
        envelope consumed by modelo calculation.
    :mod:`application.modelo`
        Work-unit calculation actions that call
        :func:`preflight_ledger_tax_readiness` before resolving
        ledger-backed bindings for a :class:`domain.modelos.WorkUnit`.
    :mod:`domain.transactions`
        The transaction catalogue and lifecycle states that remain the ledger's
        durable movement authority.
    :mod:`domain.categories`
        Closed spending-category identifiers and proportionality rules accepted
        by ledger ``category_id`` and ratio workflows.
    :mod:`domain.usage_ratios`
        Bucket-scoped, encrypted per-category business-use ratios validated by
        ledger commands and preflight.
    :mod:`domain.iva`
        Legal IVA classification and prorrata substrates referenced by ledger
        tax fields without becoming ledger lifecycle ownership.
"""

from __future__ import annotations

from ...core.external_constants import CLASSIFIED_BY_MANUAL
from ..export import ExportSerializationFormat
from ._actions_classification import add_classification_rule, apply_classification_rules, bulk_classify_from_csv
from ._actions_export import export_ledger_transactions
from ._actions_import import LedgerProviderID, import_ledger_source, import_ledger_transactions
from ._actions_lifecycle import (
    archive_manual_transaction,
    mark_transaction_reviewed_excluded,
    remove_manual_transaction,
    reset_ledger_catalogue,
    restore_manual_transaction,
    stash_manual_transaction,
)
from ._actions_manual import (
    attach_manual_transaction_evidence,
    create_manual_transaction,
    get_manual_transaction,
    ledger_transaction_payload,
    ledger_transaction_result_payload,
    ledger_transaction_review_payload,
    ledger_transaction_tracking_payload,
    link_manual_transaction_invoice,
    list_manual_transactions,
    query_ledger_review_rows,
    summarize_manual_transactions,
    update_manual_transaction,
    update_manual_transaction_fields,
)
from ._actions_split_merge import (
    merge_transactions,
    split_transaction,
    split_transaction_with_classified_children,
)
from ._business_operation_invoice import (
    BusinessOperationInvoice,
    BusinessOperationInvoiceDirection,
    BusinessOperationInvoiceDocument,
    BusinessOperationInvoiceInputError,
    BusinessOperationInvoiceNotFoundError,
    BusinessOperationInvoicePatch,
    BusinessOperationInvoiceRepository,
    BusinessOperationInvoiceResult,
    CollectibleInvoiceService,
    PayableInvoiceService,
    validate_eu_iva_id,
)
from ._evidence import (
    MediaKind,
    PurchaseInvoiceEvidence,
    PurchaseInvoiceEvidenceDocument,
    PurchaseInvoiceEvidenceInputError,
    PurchaseInvoiceEvidenceNotFoundError,
    PurchaseInvoiceEvidencePatch,
    PurchaseInvoiceEvidenceRepository,
    PurchaseInvoiceEvidenceService,
)
from ._evidence_draft import (
    InvoiceConfirmationResult,
    InvoiceDraft,
    confirm_invoice_draft_from_evidence,
    extract_invoice_draft_from_evidence,
    extract_invoice_fields,
)
from ._id_resolution import (
    MINIMUM_DISPLAY_ID_WIDTH,
    compute_display_id_width,
    resolve_lineage_transaction_id,
    resolve_transaction_id,
)
from ._llm_classification import (
    LLMClassificationSuggestion,
    LLMProvider,
    LLMProviderAvailability,
    LLMSaturatedSuggestion,
    LLMSplitApplyResult,
    LLMSplitChildSuggestion,
    LLMSplitSuggestion,
    LLMSuggestionRejectionResult,
    OperatorIvaDerivationResult,
    apply_evidence_classification,
    apply_evidence_split,
    apply_llm_classification,
    apply_saturated_llm_classification,
    available_llm_providers,
    derive_operator_iva_substrate,
    is_llm_provider_available,
    reject_llm_suggestion,
    saturate_llm_classification,
    suggest_evidence_split,
    suggest_llm_classification,
)
from ._llm_diagnostics import (
    DEFAULT_LOW_CONFIDENCE_THRESHOLD,
    LlmConfidenceProviderMetrics,
    LlmDiagnosticsReport,
    LlmUsageProviderMetrics,
    build_llm_diagnostics_report,
)
from ._models import (
    BULK_CLASSIFY_ALLOWED_COLUMNS,
    ApplyRulesAppliedRow,
    ApplyRulesResult,
    BulkClassifyFailure,
    BulkClassifyResult,
    BulkClassifyRow,
    LedgerCatalogueResetReport,
    LedgerExportCommand,
    LedgerExportResult,
    LedgerExportRow,
    LedgerImportDiagnosticReport,
    LedgerImportOperationResult,
    LedgerRemovalBlocker,
    LedgerReviewQuery,
    LedgerReviewQueryResult,
    LedgerReviewRow,
    LedgerSourceImportCommand,
    LedgerSourceImportResult,
    LedgerSourceValidationReport,
    LedgerSourceVerificationReport,
    LedgerStatusReport,
    LedgerTransactionPayload,
    LedgerTransactionRemovalReport,
    LedgerTransactionResultPayload,
    LedgerTransactionReviewPayload,
    LedgerTransactionTrackingPayload,
    ManualLedgerTransactionCommand,
    ManualLedgerTransactionPatch,
    ManualLedgerTransactionResult,
    MergeTransactionsResult,
    SplitChildCommand,
    SplitTransactionResult,
)
from ._participation_read import get_transaction_participation
from ._preflight import (
    LedgerPreflightIssue,
    LedgerPreflightIssueReason,
    LedgerPreflightReport,
    preflight_ledger_tax_readiness,
    preflight_transaction_catalogue,
)
from ._ratios import (
    EligibleCategoryRow,
    RatiosCensoOverrideWarning,
    RatiosValidationFinding,
    RatiosValidationReport,
    censo_business_pct_for,
    censo_override_warning,
    eligible_ratio_categories,
    list_eligible_ratios_for_bucket,
    set_usage_ratio,
    unset_usage_ratio,
    validate_ratios_for_bucket,
    validate_ratios_profile,
)
from ._review_projection import ledger_transaction_review_status
from ._rule_repository import LedgerClassificationRuleRepository

__all__ = [
    "BULK_CLASSIFY_ALLOWED_COLUMNS",
    "CLASSIFIED_BY_MANUAL",
    "DEFAULT_LOW_CONFIDENCE_THRESHOLD",
    "MINIMUM_DISPLAY_ID_WIDTH",
    "ApplyRulesAppliedRow",
    "ApplyRulesResult",
    "BulkClassifyFailure",
    "BulkClassifyResult",
    "BulkClassifyRow",
    "BusinessOperationInvoice",
    "BusinessOperationInvoiceDirection",
    "BusinessOperationInvoiceDocument",
    "BusinessOperationInvoiceInputError",
    "BusinessOperationInvoiceNotFoundError",
    "BusinessOperationInvoicePatch",
    "BusinessOperationInvoiceRepository",
    "BusinessOperationInvoiceResult",
    "CollectibleInvoiceService",
    "EligibleCategoryRow",
    "ExportSerializationFormat",
    "InvoiceConfirmationResult",
    "InvoiceDraft",
    "LLMClassificationSuggestion",
    "LLMProvider",
    "LLMProviderAvailability",
    "LLMSaturatedSuggestion",
    "LLMSplitApplyResult",
    "LLMSplitChildSuggestion",
    "LLMSplitSuggestion",
    "LLMSuggestionRejectionResult",
    "LedgerCatalogueResetReport",
    "LedgerClassificationRuleRepository",
    "LedgerExportCommand",
    "LedgerExportResult",
    "LedgerExportRow",
    "LedgerImportDiagnosticReport",
    "LedgerImportOperationResult",
    "LedgerPreflightIssue",
    "LedgerPreflightIssueReason",
    "LedgerPreflightReport",
    "LedgerProviderID",
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
    "LlmConfidenceProviderMetrics",
    "LlmDiagnosticsReport",
    "LlmUsageProviderMetrics",
    "ManualLedgerTransactionCommand",
    "ManualLedgerTransactionPatch",
    "ManualLedgerTransactionResult",
    "MediaKind",
    "MergeTransactionsResult",
    "OperatorIvaDerivationResult",
    "PayableInvoiceService",
    "PurchaseInvoiceEvidence",
    "PurchaseInvoiceEvidenceDocument",
    "PurchaseInvoiceEvidenceInputError",
    "PurchaseInvoiceEvidenceNotFoundError",
    "PurchaseInvoiceEvidencePatch",
    "PurchaseInvoiceEvidenceRepository",
    "PurchaseInvoiceEvidenceService",
    "RatiosCensoOverrideWarning",
    "RatiosValidationFinding",
    "RatiosValidationReport",
    "SplitChildCommand",
    "SplitTransactionResult",
    "add_classification_rule",
    "apply_classification_rules",
    "apply_evidence_classification",
    "apply_evidence_split",
    "apply_llm_classification",
    "apply_saturated_llm_classification",
    "archive_manual_transaction",
    "attach_manual_transaction_evidence",
    "available_llm_providers",
    "build_llm_diagnostics_report",
    "bulk_classify_from_csv",
    "censo_business_pct_for",
    "censo_override_warning",
    "compute_display_id_width",
    "confirm_invoice_draft_from_evidence",
    "create_manual_transaction",
    "derive_operator_iva_substrate",
    "eligible_ratio_categories",
    "export_ledger_transactions",
    "extract_invoice_draft_from_evidence",
    "extract_invoice_fields",
    "get_manual_transaction",
    "get_transaction_participation",
    "import_ledger_source",
    "import_ledger_transactions",
    "is_llm_provider_available",
    "ledger_transaction_payload",
    "ledger_transaction_result_payload",
    "ledger_transaction_review_payload",
    "ledger_transaction_review_status",
    "ledger_transaction_tracking_payload",
    "link_manual_transaction_invoice",
    "list_eligible_ratios_for_bucket",
    "list_manual_transactions",
    "mark_transaction_reviewed_excluded",
    "merge_transactions",
    "preflight_ledger_tax_readiness",
    "preflight_transaction_catalogue",
    "query_ledger_review_rows",
    "reject_llm_suggestion",
    "remove_manual_transaction",
    "reset_ledger_catalogue",
    "resolve_lineage_transaction_id",
    "resolve_transaction_id",
    "restore_manual_transaction",
    "saturate_llm_classification",
    "set_usage_ratio",
    "split_transaction",
    "split_transaction_with_classified_children",
    "stash_manual_transaction",
    "suggest_evidence_split",
    "suggest_llm_classification",
    "summarize_manual_transactions",
    "unset_usage_ratio",
    "update_manual_transaction",
    "update_manual_transaction_fields",
    "validate_eu_iva_id",
    "validate_ratios_for_bucket",
    "validate_ratios_profile",
]
