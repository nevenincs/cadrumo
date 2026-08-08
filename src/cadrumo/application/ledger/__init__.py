"""Application facade for bucket-scoped ledger and invoice-adjacent workflows.

Owns the operator-facing ledger lifecycle: importing bank statements and
records, classifying transactions for tax, splitting and merging entries,
attaching evidence, and checking a period's tax-readiness before a modelo
calculation consumes it. The primary movement fact remains
``ledger_transaction``. Purchase invoice evidence is a related bucket-scoped
record, not a ledger row.

This package owns no invoice record of its own. Invoices live in exactly one
place -- the :class:`domain.invoices.Invoice` aggregate, held in an
:class:`domain.invoices.InvoiceCatalogue` and driven by
:mod:`application.invoices`. The issued / received direction maps onto
:attr:`core.BindingSourceKind.COLLECTIBLE_INVOICE` and
:attr:`core.BindingSourceKind.PAYABLE_INVOICE` through
:func:`application.invoices.invoice_direction_to_source_kind`, which is the one
home for that mapping.

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
  ledger transactions, and :func:`extract_invoice_draft_from_evidence` with
  :class:`InvoiceDraft` - the on-host document-reading entry point an operator
  reviews before minting a :class:`domain.invoices.Invoice` from a PDF.
* :class:`EvidenceInput` - the transient in-memory carrier of decrypted
  evidence bytes that :func:`transcribe_text_layer` reads. Exported because
  it is that function's argument type: a consumer cannot construct a call
  through this facade without it. It is never persisted or serialized.
* :class:`DocumentTranscription` with :class:`TranscriberIdentity` - the
  acquisition-stage record of a document's reading-order text, printed forms
  preserved, stamped with the reader that produced it. Exported because the
  vision reader outside this package produces one and every later ingestion
  stage consumes one. Like :class:`EvidenceInput` it refuses serialization.
* :func:`confirm_invoice_draft_from_evidence` with
  :class:`InvoiceConfirmationResult` - the non-interactive confirm step that
  re-extracts a draft, layers operator overrides on top, and delegates the
  actual write to :func:`application.invoices.create_catalogue_invoice`.
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

from typing import TYPE_CHECKING

from ...core.external_constants import CLASSIFIED_BY_MANUAL

if TYPE_CHECKING:
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
    from ._aeat_record_projection import (
        AeatRecordProjectionError,
        describe_aeat_party_identifier,
        project_aeat_record_counterparty,
    )
    from ._batch_ingest import (
        BATCH_ITEM_STATUSES,
        BatchItemResult,
        BatchRunResult,
        InferencePause,
        UnresolvedBatchSource,
        batch_item_identity,
        order_batch_items,
        order_batch_sources,
        run_evidence_batch,
        summarise_batch,
    )
    from ._closure_findings import (
        ROUNDING_ALLOWANCE_PER_TERM,
        closure_findings,
        within_rounding_allowance,
    )
    from ._confirmation_gate import (
        BLOCKING_REASON_BY_DISCREPANCY_KIND,
        IDENTITY_FIELDS,
        ConfirmationBlockedError,
        ConfirmationBlocker,
        FindingResolution,
        confirmation_blockers,
        resolved_blockers,
    )
    from ._classification_assembly import (
        ClassificationAssembly,
        DeclaredFact,
        DeclaredFacts,
        MissingClassifierInput,
        assemble_classification_criteria,
        classify_from_assembled_criteria,
    )
    from ._classifier_inputs import ClassifierInputs, collect_classifier_inputs
    from ._establishment_ladder import (
        CounterpartyEstablishment,
        EstablishmentRung,
        resolve_counterparty_establishment_scope,
        resolve_draft_counterparty_establishment,
    )
    from ._counterparty_establishment import (
        CounterpartyEstablishmentConflictError,
        CounterpartyEstablishmentContradiction,
        CounterpartyEstablishmentFact,
        CounterpartyEstablishmentInputError,
        CounterpartyEstablishmentRepository,
        CounterpartyEstablishmentResolution,
        counterparty_establishment_key,
        forget_counterparty_establishment,
        record_counterparty_establishment,
        resolve_counterparty_establishment,
    )
    from ._confirmation_record import (
        ConfirmationRecordDocument,
        ConfirmationRecordRepository,
        FieldAssertion,
        InvoiceConfirmationRecord,
        ResolvedFinding,
        build_confirmation_record,
        derive_confirmation_id,
        field_assertions,
        load_confirmation_records,
        re_stamped_provenance,
        read_confirmation_record,
        write_confirmation_record,
    )
    from ._consent_withdrawal import (
        CloudDerivedArtefact,
        ConsentedDispatch,
        ConsentWithdrawalSurvey,
        LocalRederivation,
        OnHostReader,
        artefact_is_cloud_derived,
        rederive_artefact_on_host,
        survey_cloud_consent,
    )
    from ._deterministic_findings import (
        DETERMINISTIC_CHECKS,
        DeterministicCheck,
        deterministic_check_names,
        deterministic_findings,
    )
    from ._document_transcription import DocumentTranscription, TranscriberIdentity
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
        DraftDiscrepancyFinding,
        FieldAmbiguityCandidate,
        FieldProvenance,
        InvoiceConfirmationResult,
        InvoiceDraft,
        InvoiceDraftLine,
        InvoiceDraftRateBreakdown,
        PrintedTotalDiscrepancy,
        confirm_invoice_draft_from_evidence,
        extract_invoice_draft_from_evidence,
        printed_total_discrepancy,
    )
    from ._evidence_input import EvidenceInput
    from ._evidence_textlayer import text_layer_transcriber_identity, transcribe_text_layer
    from ._extraction_draft_store import (
        ExtractionDraftDocument,
        ExtractionDraftRepository,
        StoredExtractionDraft,
        discard_extraction_draft,
        load_extraction_drafts,
        read_extraction_draft,
        write_extraction_draft,
    )
    from ._grounded_reading import (
        GROUNDABLE_ORIGINS,
        ground_draft_against_transcription,
        verified_provenance,
    )
    from ._grounding_anchor import (
        AnchorEvaluation,
        evaluate_anchor,
        ground_ambiguous_candidates,
        ground_anchored_value,
        ground_self_reported_anchor,
        normalise_for_anchor_search,
        printed_excerpt_occurs,
        strip_printed_unit,
    )
    from ._filer_establishment import FILER_POSTCODE_FACT_PATH, resolve_filer_territorial_scope
    from ._id_resolution import (
        MINIMUM_DISPLAY_ID_WIDTH,
        compute_display_id_width,
        resolve_lineage_transaction_id,
        resolve_transaction_id,
    )
    from ._identity_roles import (
        IdentityCandidate,
        IdentityRoleResolution,
        canonical_identity_token,
        resolve_counterparty_identity,
    )
    from ._llm_classification import (
        apply_evidence_classification,
        apply_evidence_split,
        apply_llm_classification,
        apply_saturated_llm_classification,
        derive_operator_iva_substrate,
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
    from ._llm_review_workflow import (
        InvoiceDraftDeclineResult,
        LlmReviewDecision,
        LlmReviewInvocationOrigin,
        LlmReviewRequest,
        LlmReviewResult,
        ReviewedInvoiceDraft,
        ReviewedSuggestion,
        execute_reviewed_decision,
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
    from ._regime_contradiction import draft_prints_a_repercutido_line, regime_contradiction_finding
    from ._review_projection import ledger_transaction_review_status
    from ._rule_repository import LedgerClassificationRuleRepository


#: Public name -> owning submodule, resolved on first attribute access.
_LAZY_EXPORTS: dict[str, str] = {
    "CloudDerivedArtefact": "._consent_withdrawal",
    "ConsentWithdrawalSurvey": "._consent_withdrawal",
    "ConsentedDispatch": "._consent_withdrawal",
    "LocalRederivation": "._consent_withdrawal",
    "OnHostReader": "._consent_withdrawal",
    "artefact_is_cloud_derived": "._consent_withdrawal",
    "rederive_artefact_on_host": "._consent_withdrawal",
    "survey_cloud_consent": "._consent_withdrawal",
    "ApplyRulesAppliedRow": "._models",
    "ApplyRulesResult": "._models",
    "BULK_CLASSIFY_ALLOWED_COLUMNS": "._models",
    "BulkClassifyFailure": "._models",
    "BulkClassifyResult": "._models",
    "BulkClassifyRow": "._models",
    "DEFAULT_LOW_CONFIDENCE_THRESHOLD": "._llm_diagnostics",
    "AeatRecordProjectionError": "._aeat_record_projection",
    "ExtractionDraftDocument": "._extraction_draft_store",
    "ExtractionDraftRepository": "._extraction_draft_store",
    "StoredExtractionDraft": "._extraction_draft_store",
    "discard_extraction_draft": "._extraction_draft_store",
    "load_extraction_drafts": "._extraction_draft_store",
    "read_extraction_draft": "._extraction_draft_store",
    "write_extraction_draft": "._extraction_draft_store",
    "BLOCKING_REASON_BY_DISCREPANCY_KIND": "._confirmation_gate",
    "IDENTITY_FIELDS": "._confirmation_gate",
    "ConfirmationBlockedError": "._confirmation_gate",
    "ConfirmationBlocker": "._confirmation_gate",
    "FindingResolution": "._confirmation_gate",
    "confirmation_blockers": "._confirmation_gate",
    "resolved_blockers": "._confirmation_gate",
    "ClassificationAssembly": "._classification_assembly",
    "DeclaredFact": "._classification_assembly",
    "DeclaredFacts": "._classification_assembly",
    "MissingClassifierInput": "._classification_assembly",
    "assemble_classification_criteria": "._classification_assembly",
    "classify_from_assembled_criteria": "._classification_assembly",
    "ClassifierInputs": "._classifier_inputs",
    "collect_classifier_inputs": "._classifier_inputs",
    "CounterpartyEstablishment": "._establishment_ladder",
    "EstablishmentRung": "._establishment_ladder",
    "resolve_counterparty_establishment_scope": "._establishment_ladder",
    "resolve_draft_counterparty_establishment": "._establishment_ladder",
    "CounterpartyDraftSide": "._evidence_draft",
    "counterparty_draft_side": "._evidence_draft",
    "CounterpartyEstablishmentConflictError": "._counterparty_establishment",
    "CounterpartyEstablishmentContradiction": "._counterparty_establishment",
    "CounterpartyEstablishmentFact": "._counterparty_establishment",
    "CounterpartyEstablishmentInputError": "._counterparty_establishment",
    "CounterpartyEstablishmentRepository": "._counterparty_establishment",
    "CounterpartyEstablishmentResolution": "._counterparty_establishment",
    "counterparty_establishment_key": "._counterparty_establishment",
    "forget_counterparty_establishment": "._counterparty_establishment",
    "record_counterparty_establishment": "._counterparty_establishment",
    "resolve_counterparty_establishment": "._counterparty_establishment",
    "ConfirmationRecordDocument": "._confirmation_record",
    "ConfirmationRecordRepository": "._confirmation_record",
    "FieldAssertion": "._confirmation_record",
    "InvoiceConfirmationRecord": "._confirmation_record",
    "ResolvedFinding": "._confirmation_record",
    "build_confirmation_record": "._confirmation_record",
    "derive_confirmation_id": "._confirmation_record",
    "field_assertions": "._confirmation_record",
    "load_confirmation_records": "._confirmation_record",
    "re_stamped_provenance": "._confirmation_record",
    "read_confirmation_record": "._confirmation_record",
    "write_confirmation_record": "._confirmation_record",
    "ROUNDING_ALLOWANCE_PER_TERM": "._closure_findings",
    "closure_findings": "._closure_findings",
    "DETERMINISTIC_CHECKS": "._deterministic_findings",
    "DeterministicCheck": "._deterministic_findings",
    "deterministic_check_names": "._deterministic_findings",
    "deterministic_findings": "._deterministic_findings",
    "within_rounding_allowance": "._closure_findings",
    "AnchorEvaluation": "._grounding_anchor",
    "evaluate_anchor": "._grounding_anchor",
    "GROUNDABLE_ORIGINS": "._grounded_reading",
    "ground_ambiguous_candidates": "._grounding_anchor",
    "ground_draft_against_transcription": "._grounded_reading",
    "verified_provenance": "._grounded_reading",
    "ground_anchored_value": "._grounding_anchor",
    "ground_self_reported_anchor": "._grounding_anchor",
    "normalise_for_anchor_search": "._grounding_anchor",
    "printed_excerpt_occurs": "._grounding_anchor",
    "strip_printed_unit": "._grounding_anchor",
    "IdentityCandidate": "._identity_roles",
    "IdentityRoleResolution": "._identity_roles",
    "canonical_identity_token": "._identity_roles",
    "resolve_counterparty_identity": "._identity_roles",
    "draft_prints_a_repercutido_line": "._regime_contradiction",
    "regime_contradiction_finding": "._regime_contradiction",
    "describe_aeat_party_identifier": "._aeat_record_projection",
    "project_aeat_record_counterparty": "._aeat_record_projection",
    "DocumentTranscription": "._document_transcription",
    "DraftDiscrepancyFinding": "._evidence_draft",
    "EligibleCategoryRow": "._ratios",
    "EvidenceInput": "._evidence_input",
    "ExportSerializationFormat": "..export",
    "FieldAmbiguityCandidate": "._evidence_draft",
    "BATCH_ITEM_STATUSES": "._batch_ingest",
    "BatchItemResult": "._batch_ingest",
    "BatchRunResult": "._batch_ingest",
    "InferencePause": "._batch_ingest",
    "UnresolvedBatchSource": "._batch_ingest",
    "batch_item_identity": "._batch_ingest",
    "run_evidence_batch": "._batch_ingest",
    "order_batch_items": "._batch_ingest",
    "order_batch_sources": "._batch_ingest",
    "summarise_batch": "._batch_ingest",
    "FieldProvenance": "._evidence_draft",
    "InvoiceConfirmationResult": "._evidence_draft",
    "InvoiceDraft": "._evidence_draft",
    "InvoiceDraftLine": "._evidence_draft",
    "InvoiceDraftRateBreakdown": "._evidence_draft",
    "LedgerCatalogueResetReport": "._models",
    "LedgerClassificationRuleRepository": "._rule_repository",
    "LedgerExportCommand": "._models",
    "LedgerExportResult": "._models",
    "LedgerExportRow": "._models",
    "LedgerImportDiagnosticReport": "._models",
    "LedgerImportOperationResult": "._models",
    "LedgerPreflightIssue": "._preflight",
    "LedgerPreflightIssueReason": "._preflight",
    "LedgerPreflightReport": "._preflight",
    "LedgerProviderID": "._actions_import",
    "LedgerRemovalBlocker": "._models",
    "LedgerReviewQuery": "._models",
    "LedgerReviewQueryResult": "._models",
    "LedgerReviewRow": "._models",
    "LedgerSourceImportCommand": "._models",
    "LedgerSourceImportResult": "._models",
    "LedgerSourceValidationReport": "._models",
    "LedgerSourceVerificationReport": "._models",
    "LedgerStatusReport": "._models",
    "LedgerTransactionPayload": "._models",
    "LedgerTransactionRemovalReport": "._models",
    "LedgerTransactionResultPayload": "._models",
    "LedgerTransactionReviewPayload": "._models",
    "LedgerTransactionTrackingPayload": "._models",
    "LlmConfidenceProviderMetrics": "._llm_diagnostics",
    "LlmDiagnosticsReport": "._llm_diagnostics",
    "InvoiceDraftDeclineResult": "._llm_review_workflow",
    "LlmReviewDecision": "._llm_review_workflow",
    "LlmReviewInvocationOrigin": "._llm_review_workflow",
    "LlmReviewRequest": "._llm_review_workflow",
    "LlmReviewResult": "._llm_review_workflow",
    "LlmUsageProviderMetrics": "._llm_diagnostics",
    "MINIMUM_DISPLAY_ID_WIDTH": "._id_resolution",
    "ManualLedgerTransactionCommand": "._models",
    "ManualLedgerTransactionPatch": "._models",
    "ManualLedgerTransactionResult": "._models",
    "MediaKind": "._evidence",
    "MergeTransactionsResult": "._models",
    "PrintedTotalDiscrepancy": "._evidence_draft",
    "PurchaseInvoiceEvidence": "._evidence",
    "PurchaseInvoiceEvidenceDocument": "._evidence",
    "PurchaseInvoiceEvidenceInputError": "._evidence",
    "PurchaseInvoiceEvidenceNotFoundError": "._evidence",
    "PurchaseInvoiceEvidencePatch": "._evidence",
    "PurchaseInvoiceEvidenceRepository": "._evidence",
    "PurchaseInvoiceEvidenceService": "._evidence",
    "RatiosCensoOverrideWarning": "._ratios",
    "RatiosValidationFinding": "._ratios",
    "RatiosValidationReport": "._ratios",
    "ReviewedInvoiceDraft": "._llm_review_workflow",
    "ReviewedSuggestion": "._llm_review_workflow",
    "SplitChildCommand": "._models",
    "SplitTransactionResult": "._models",
    "TranscriberIdentity": "._document_transcription",
    "add_classification_rule": "._actions_classification",
    "apply_classification_rules": "._actions_classification",
    "apply_evidence_classification": "._llm_classification",
    "apply_evidence_split": "._llm_classification",
    "apply_llm_classification": "._llm_classification",
    "apply_saturated_llm_classification": "._llm_classification",
    "archive_manual_transaction": "._actions_lifecycle",
    "attach_manual_transaction_evidence": "._actions_manual",
    "build_llm_diagnostics_report": "._llm_diagnostics",
    "bulk_classify_from_csv": "._actions_classification",
    "censo_business_pct_for": "._ratios",
    "censo_override_warning": "._ratios",
    "compute_display_id_width": "._id_resolution",
    "confirm_invoice_draft_from_evidence": "._evidence_draft",
    "create_manual_transaction": "._actions_manual",
    "derive_operator_iva_substrate": "._llm_classification",
    "eligible_ratio_categories": "._ratios",
    "execute_reviewed_decision": "._llm_review_workflow",
    "export_ledger_transactions": "._actions_export",
    "extract_invoice_draft_from_evidence": "._evidence_draft",
    "get_manual_transaction": "._actions_manual",
    "get_transaction_participation": "._participation_read",
    "import_ledger_source": "._actions_import",
    "import_ledger_transactions": "._actions_import",
    "ledger_transaction_payload": "._actions_manual",
    "ledger_transaction_result_payload": "._actions_manual",
    "ledger_transaction_review_payload": "._actions_manual",
    "ledger_transaction_review_status": "._review_projection",
    "ledger_transaction_tracking_payload": "._actions_manual",
    "link_manual_transaction_invoice": "._actions_manual",
    "list_eligible_ratios_for_bucket": "._ratios",
    "list_manual_transactions": "._actions_manual",
    "mark_transaction_reviewed_excluded": "._actions_lifecycle",
    "merge_transactions": "._actions_split_merge",
    "FILER_POSTCODE_FACT_PATH": "._filer_establishment",
    "preflight_ledger_tax_readiness": "._preflight",
    "preflight_transaction_catalogue": "._preflight",
    "printed_total_discrepancy": "._evidence_draft",
    "query_ledger_review_rows": "._actions_manual",
    "reject_llm_suggestion": "._llm_classification",
    "remove_manual_transaction": "._actions_lifecycle",
    "reset_ledger_catalogue": "._actions_lifecycle",
    "resolve_filer_territorial_scope": "._filer_establishment",
    "resolve_lineage_transaction_id": "._id_resolution",
    "resolve_transaction_id": "._id_resolution",
    "restore_manual_transaction": "._actions_lifecycle",
    "saturate_llm_classification": "._llm_classification",
    "set_usage_ratio": "._ratios",
    "split_transaction": "._actions_split_merge",
    "split_transaction_with_classified_children": "._actions_split_merge",
    "stash_manual_transaction": "._actions_lifecycle",
    "suggest_evidence_split": "._llm_classification",
    "suggest_llm_classification": "._llm_classification",
    "summarize_manual_transactions": "._actions_manual",
    "text_layer_transcriber_identity": "._evidence_textlayer",
    "transcribe_text_layer": "._evidence_textlayer",
    "unset_usage_ratio": "._ratios",
    "update_manual_transaction": "._actions_manual",
    "update_manual_transaction_fields": "._actions_manual",
    "validate_ratios_for_bucket": "._ratios",
    "validate_ratios_profile": "._ratios",
}


def __getattr__(name: str) -> object:
    """Resolve one public name by importing only the submodule that owns it.

    This facade re-exports 142 names across 20 submodules, and importing it
    eagerly pulled all of them plus their transitive graph -- 728 modules and
    about 1.6 s -- whichever single action the caller actually wanted. A CLI
    process runs one command, so nearly all of that was paid for symbols it
    never touched.

    The resolved value is written into module globals, so only the first
    access to a name goes through this hook; every later one is an ordinary
    global lookup with no import machinery in the path.

    Ownership is unchanged: every name still has exactly one canonical home in
    this package's ``__all__``, and consumers still import it from here. Only
    WHEN the owning submodule executes has moved.
    """
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    value = getattr(import_module(module_name, __name__), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Report the full public surface, including names not yet resolved."""
    return sorted(set(__all__) | set(globals()))


__all__ = [
    "BATCH_ITEM_STATUSES",
    "BLOCKING_REASON_BY_DISCREPANCY_KIND",
    "BULK_CLASSIFY_ALLOWED_COLUMNS",
    "CLASSIFIED_BY_MANUAL",
    "DEFAULT_LOW_CONFIDENCE_THRESHOLD",
    "DETERMINISTIC_CHECKS",
    "FILER_POSTCODE_FACT_PATH",
    "GROUNDABLE_ORIGINS",
    "IDENTITY_FIELDS",
    "MINIMUM_DISPLAY_ID_WIDTH",
    "ROUNDING_ALLOWANCE_PER_TERM",
    "AeatRecordProjectionError",
    "AnchorEvaluation",
    "ApplyRulesAppliedRow",
    "ApplyRulesResult",
    "BatchItemResult",
    "BatchRunResult",
    "BulkClassifyFailure",
    "BulkClassifyResult",
    "BulkClassifyRow",
    "ClassificationAssembly",
    "ClassifierInputs",
    "CloudDerivedArtefact",
    "ConfirmationBlockedError",
    "ConfirmationBlocker",
    "CounterpartyDraftSide",
    "CounterpartyEstablishment",
    "CounterpartyEstablishmentConflictError",
    "CounterpartyEstablishmentContradiction",
    "CounterpartyEstablishmentFact",
    "CounterpartyEstablishmentInputError",
    "CounterpartyEstablishmentRepository",
    "CounterpartyEstablishmentResolution",
    "ConfirmationRecordDocument",
    "ConfirmationRecordRepository",
    "ConsentWithdrawalSurvey",
    "ConsentedDispatch",
    "DeclaredFact",
    "DeclaredFacts",
    "DeterministicCheck",
    "DocumentTranscription",
    "EstablishmentRung",
    "MissingClassifierInput",
    "DraftDiscrepancyFinding",
    "EligibleCategoryRow",
    "EvidenceInput",
    "ExportSerializationFormat",
    "ExtractionDraftDocument",
    "ExtractionDraftRepository",
    "FieldAmbiguityCandidate",
    "FieldAssertion",
    "FieldProvenance",
    "FindingResolution",
    "IdentityCandidate",
    "IdentityRoleResolution",
    "InferencePause",
    "InvoiceConfirmationRecord",
    "InvoiceConfirmationResult",
    "InvoiceDraft",
    "InvoiceDraftDeclineResult",
    "InvoiceDraftLine",
    "InvoiceDraftRateBreakdown",
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
    "LlmReviewDecision",
    "LlmReviewInvocationOrigin",
    "LlmReviewRequest",
    "LlmReviewResult",
    "LlmUsageProviderMetrics",
    "LocalRederivation",
    "ManualLedgerTransactionCommand",
    "ManualLedgerTransactionPatch",
    "ManualLedgerTransactionResult",
    "MediaKind",
    "MergeTransactionsResult",
    "OnHostReader",
    "PrintedTotalDiscrepancy",
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
    "ResolvedFinding",
    "ReviewedInvoiceDraft",
    "ReviewedSuggestion",
    "SplitChildCommand",
    "SplitTransactionResult",
    "StoredExtractionDraft",
    "TranscriberIdentity",
    "UnresolvedBatchSource",
    "add_classification_rule",
    "apply_classification_rules",
    "apply_evidence_classification",
    "apply_evidence_split",
    "apply_llm_classification",
    "apply_saturated_llm_classification",
    "archive_manual_transaction",
    "artefact_is_cloud_derived",
    "attach_manual_transaction_evidence",
    "batch_item_identity",
    "build_confirmation_record",
    "build_llm_diagnostics_report",
    "bulk_classify_from_csv",
    "canonical_identity_token",
    "assemble_classification_criteria",
    "censo_business_pct_for",
    "censo_override_warning",
    "classify_from_assembled_criteria",
    "closure_findings",
    "collect_classifier_inputs",
    "compute_display_id_width",
    "confirm_invoice_draft_from_evidence",
    "confirmation_blockers",
    "counterparty_draft_side",
    "counterparty_establishment_key",
    "forget_counterparty_establishment",
    "record_counterparty_establishment",
    "resolve_counterparty_establishment",
    "resolve_counterparty_establishment_scope",
    "resolve_draft_counterparty_establishment",
    "create_manual_transaction",
    "derive_confirmation_id",
    "derive_operator_iva_substrate",
    "describe_aeat_party_identifier",
    "deterministic_check_names",
    "deterministic_findings",
    "discard_extraction_draft",
    "draft_prints_a_repercutido_line",
    "eligible_ratio_categories",
    "evaluate_anchor",
    "execute_reviewed_decision",
    "export_ledger_transactions",
    "extract_invoice_draft_from_evidence",
    "field_assertions",
    "get_manual_transaction",
    "get_transaction_participation",
    "ground_ambiguous_candidates",
    "ground_anchored_value",
    "ground_draft_against_transcription",
    "ground_self_reported_anchor",
    "import_ledger_source",
    "import_ledger_transactions",
    "ledger_transaction_payload",
    "ledger_transaction_result_payload",
    "ledger_transaction_review_payload",
    "ledger_transaction_review_status",
    "ledger_transaction_tracking_payload",
    "link_manual_transaction_invoice",
    "list_eligible_ratios_for_bucket",
    "list_manual_transactions",
    "load_confirmation_records",
    "load_extraction_drafts",
    "mark_transaction_reviewed_excluded",
    "merge_transactions",
    "normalise_for_anchor_search",
    "order_batch_items",
    "order_batch_sources",
    "preflight_ledger_tax_readiness",
    "preflight_transaction_catalogue",
    "printed_excerpt_occurs",
    "printed_total_discrepancy",
    "project_aeat_record_counterparty",
    "query_ledger_review_rows",
    "re_stamped_provenance",
    "read_confirmation_record",
    "read_extraction_draft",
    "rederive_artefact_on_host",
    "regime_contradiction_finding",
    "reject_llm_suggestion",
    "remove_manual_transaction",
    "reset_ledger_catalogue",
    "resolve_counterparty_identity",
    "resolve_filer_territorial_scope",
    "resolve_lineage_transaction_id",
    "resolve_transaction_id",
    "resolved_blockers",
    "restore_manual_transaction",
    "run_evidence_batch",
    "saturate_llm_classification",
    "set_usage_ratio",
    "split_transaction",
    "split_transaction_with_classified_children",
    "stash_manual_transaction",
    "strip_printed_unit",
    "suggest_evidence_split",
    "suggest_llm_classification",
    "summarise_batch",
    "summarize_manual_transactions",
    "survey_cloud_consent",
    "text_layer_transcriber_identity",
    "transcribe_text_layer",
    "unset_usage_ratio",
    "update_manual_transaction",
    "update_manual_transaction_fields",
    "validate_ratios_for_bucket",
    "validate_ratios_profile",
    "verified_provenance",
    "within_rounding_allowance",
    "write_confirmation_record",
    "write_extraction_draft",
]
