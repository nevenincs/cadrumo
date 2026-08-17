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

from collections.abc import Callable
from functools import partial
from importlib import import_module
from types import ModuleType
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
        detach_manual_transaction_attachments,
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
    from ._classification_assembly import (
        ClassificationAssembly,
        DeclaredFact,
        DeclaredFacts,
        IvaCategoryResolution,
        MissingClassifierInput,
        assemble_classification_criteria,
        classify_from_assembled_criteria,
        declared_category_from_document_record,
        resolve_ingestion_iva_category,
    )
    from ._classifier_inputs import ClassifierInputs, collect_classifier_inputs
    from ._closure_findings import (
        ROUNDING_ALLOWANCE_PER_TERM,
        closure_findings,
        within_rounding_allowance,
    )
    from ._confirm_establishment import ConfirmedEstablishment, resolve_confirmed_establishment
    from ._confirmation_gate import (
        BLOCKING_REASON_BY_DISCREPANCY_KIND,
        IDENTITY_FIELDS,
        ConfirmationBlockedError,
        ConfirmationBlocker,
        FindingResolution,
        confirmation_blockers,
        resolved_blockers,
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
        ConsentRederivationError,
        ConsentWithdrawalSurvey,
        LocalRederivation,
        OnHostReader,
        artefact_is_cloud_derived,
        rederive_artefact_on_host,
        survey_cloud_consent,
    )
    from ._counterparty_establishment import (
        ConfirmedCounterpartyFacts,
        ConfirmedCounterpartyFactsInputError,
        ConfirmedCounterpartyFactsRepository,
        ConfirmedCounterpartyResolution,
        CounterpartyEstablishmentConflictError,
        CounterpartyEstablishmentContradiction,
        confirmed_counterparty_facts_key,
        forget_confirmed_counterparty_facts,
        record_confirmed_counterparty_facts,
        resolve_confirmed_counterparty_facts,
    )
    from ._country_vocabulary_advisory import (
        COUNTRY_VOCABULARY_ADVISED_STATUSES,
        CountryVocabularyAdvisory,
        CountryVocabularyWarning,
        country_vocabulary_advisory,
    )
    from ._deterministic_findings import (
        DETERMINISTIC_CHECKS,
        DeterministicCheck,
        deterministic_check_names,
        deterministic_findings,
    )
    from ._document_direction import (
        DIRECTION_BY_FILER_ROLE,
        DirectionDerivationOutcome,
        InvoiceKindDerivation,
        derive_invoice_kind_from_filer_role,
    )
    from ._document_transcription import DocumentTranscription, TranscriberIdentity
    from ._establishment_ladder import (
        CounterpartyEstablishment,
        EstablishmentRung,
        RegistrationEstablishmentConflict,
        resolve_counterparty_establishment_scope,
        resolve_draft_counterparty_establishment,
        scope_printed_evidence_would_establish,
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
        CounterpartyDraftSide,
        DraftDiscrepancyFinding,
        FieldAmbiguityCandidate,
        FieldProvenance,
        InvoiceConfirmationResult,
        InvoiceDraft,
        InvoiceDraftLine,
        InvoiceDraftRateBreakdown,
        PrintedTotalDiscrepancy,
        confirm_invoice_draft_from_evidence,
        counterparty_draft_side,
        extract_invoice_draft_from_evidence,
        printed_total_discrepancy,
    )
    from ._evidence_input import EvidenceInput
    from ._evidence_textlayer import text_layer_transcriber_identity, transcribe_text_layer
    from ._extracted_document_cache import ExtractedDocumentCacheRepository, write_cached_transcription
    from ._extraction_draft_store import (
        ExtractionDraftDocument,
        ExtractionDraftRepository,
        StoredExtractionDraft,
        discard_extraction_draft,
        load_extraction_drafts,
        read_extraction_draft,
        write_extraction_draft,
    )
    from ._filer_establishment import (
        FILER_POSTCODE_FACT_PATH,
        FILER_TAX_ID_FACT_PATH,
        resolve_filer_tax_id,
        resolve_filer_territorial_scope,
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
        printed_excerpt_occurs_in_text,
        strip_printed_unit,
    )
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
    from ._invoice_extraction_authority import (
        InvoiceExtractionAuthorityValues,
        default_invoice_extraction_period,
        resolve_invoice_extraction_authority_values,
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
        LlmUsageCostProviderMetrics,
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
    from ._party_attribution import (
        ATTRIBUTION_ESTABLISHING_ORIGINS,
        PARTY_ATTRIBUTED_ADDRESS_FIELDS,
        PartyAddress,
        PartyAttributionAdvisory,
        PartyAttributionWarning,
        party_addresses,
        party_attribution_advisory,
        stamp_unverified_party_attribution,
    )
    from ._party_colocation import (
        PartyAttributionOutcome,
        PartyColocationResolution,
        party_attribution_findings,
        party_regions,
        resolve_party_attribution_by_colocation,
    )
    from ._preconditions import (
        LedgerPreconditionCondition,
        ledger_no_recovery_verdict,
    )
    from ._preflight import (
        OPERATOR_ACTION_BY_IVA_LEDGER_AGGREGATION_ISSUE,
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
    from ._review_advisories import review_advisory_kinds
    from ._review_projection import ledger_transaction_review_status
    from ._rule_repository import LedgerClassificationRuleRepository


#: Public name -> owning submodule, resolved on first attribute access.
_LAZY_EXPORTS: dict[str, str] = {
    "CloudDerivedArtefact": "._consent_withdrawal",
    "ConsentRederivationError": "._consent_withdrawal",
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
    "ExtractedDocumentCacheRepository": "._extracted_document_cache",
    "write_cached_transcription": "._extracted_document_cache",
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
    "declared_category_from_document_record": "._classification_assembly",
    "IvaCategoryResolution": "._classification_assembly",
    "resolve_ingestion_iva_category": "._classification_assembly",
    "ClassifierInputs": "._classifier_inputs",
    "collect_classifier_inputs": "._classifier_inputs",
    "ConfirmedEstablishment": "._confirm_establishment",
    "resolve_confirmed_establishment": "._confirm_establishment",
    "CounterpartyEstablishment": "._establishment_ladder",
    "EstablishmentRung": "._establishment_ladder",
    "RegistrationEstablishmentConflict": "._establishment_ladder",
    "resolve_counterparty_establishment_scope": "._establishment_ladder",
    "resolve_draft_counterparty_establishment": "._establishment_ladder",
    "scope_printed_evidence_would_establish": "._establishment_ladder",
    "FILER_TAX_ID_FACT_PATH": "._filer_establishment",
    "resolve_filer_tax_id": "._filer_establishment",
    "DIRECTION_BY_FILER_ROLE": "._document_direction",
    "DirectionDerivationOutcome": "._document_direction",
    "InvoiceKindDerivation": "._document_direction",
    "derive_invoice_kind_from_filer_role": "._document_direction",
    "COUNTRY_VOCABULARY_ADVISED_STATUSES": "._country_vocabulary_advisory",
    "CountryVocabularyAdvisory": "._country_vocabulary_advisory",
    "CountryVocabularyWarning": "._country_vocabulary_advisory",
    "country_vocabulary_advisory": "._country_vocabulary_advisory",
    "ATTRIBUTION_ESTABLISHING_ORIGINS": "._party_attribution",
    "PARTY_ATTRIBUTED_ADDRESS_FIELDS": "._party_attribution",
    "PartyAddress": "._party_attribution",
    "party_addresses": "._party_attribution",
    "PartyAttributionOutcome": "._party_colocation",
    "PartyColocationResolution": "._party_colocation",
    "party_attribution_findings": "._party_colocation",
    "party_regions": "._party_colocation",
    "resolve_party_attribution_by_colocation": "._party_colocation",
    "PartyAttributionAdvisory": "._party_attribution",
    "PartyAttributionWarning": "._party_attribution",
    "party_attribution_advisory": "._party_attribution",
    "stamp_unverified_party_attribution": "._party_attribution",
    "review_advisory_kinds": "._review_advisories",
    "CounterpartyDraftSide": "._evidence_draft",
    "counterparty_draft_side": "._evidence_draft",
    "CounterpartyEstablishmentConflictError": "._counterparty_establishment",
    "CounterpartyEstablishmentContradiction": "._counterparty_establishment",
    "ConfirmedCounterpartyFacts": "._counterparty_establishment",
    "ConfirmedCounterpartyFactsInputError": "._counterparty_establishment",
    "ConfirmedCounterpartyFactsRepository": "._counterparty_establishment",
    "ConfirmedCounterpartyResolution": "._counterparty_establishment",
    "confirmed_counterparty_facts_key": "._counterparty_establishment",
    "forget_confirmed_counterparty_facts": "._counterparty_establishment",
    "record_confirmed_counterparty_facts": "._counterparty_establishment",
    "resolve_confirmed_counterparty_facts": "._counterparty_establishment",
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
    "printed_excerpt_occurs_in_text": "._grounding_anchor",
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
    "InvoiceExtractionAuthorityValues": "._invoice_extraction_authority",
    "resolve_invoice_extraction_authority_values": "._invoice_extraction_authority",
    "default_invoice_extraction_period": "._invoice_extraction_authority",
    "LedgerCatalogueResetReport": "._models",
    "LedgerClassificationRuleRepository": "._rule_repository",
    "LedgerExportCommand": "._models",
    "LedgerExportResult": "._models",
    "LedgerExportRow": "._models",
    "LedgerImportDiagnosticReport": "._models",
    "LedgerImportOperationResult": "._models",
    "LedgerPreconditionCondition": "._preconditions",
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
    "LlmUsageCostProviderMetrics": "._llm_diagnostics",
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
    "detach_manual_transaction_attachments": "._actions_manual",
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
    "ledger_no_recovery_verdict": "._preconditions",
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
    "OPERATOR_ACTION_BY_IVA_LEDGER_AGGREGATION_ISSUE": "._preflight",
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


# Every loader target is a closed literal from the map above.  The attribute
# name selects one of these pre-bound loaders; it never becomes an import path.
_LAZY_MODULE_LOADERS: dict[str, Callable[[], ModuleType]] = {
    module_path: partial(import_module, module_path, __name__) for module_path in frozenset(_LAZY_EXPORTS.values())
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
    loader = _LAZY_MODULE_LOADERS.get(module_name)
    if loader is None:
        raise RuntimeError(f"missing lazy loader for {module_name!r}")
    value = getattr(loader(), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Report the full public surface, including names not yet resolved."""
    return sorted(set(__all__) | set(globals()))


__all__ = [
    "ATTRIBUTION_ESTABLISHING_ORIGINS",
    "BATCH_ITEM_STATUSES",
    "BLOCKING_REASON_BY_DISCREPANCY_KIND",
    "BULK_CLASSIFY_ALLOWED_COLUMNS",
    "CLASSIFIED_BY_MANUAL",
    "COUNTRY_VOCABULARY_ADVISED_STATUSES",
    "DEFAULT_LOW_CONFIDENCE_THRESHOLD",
    "DETERMINISTIC_CHECKS",
    "DIRECTION_BY_FILER_ROLE",
    "FILER_POSTCODE_FACT_PATH",
    "FILER_TAX_ID_FACT_PATH",
    "GROUNDABLE_ORIGINS",
    "IDENTITY_FIELDS",
    "MINIMUM_DISPLAY_ID_WIDTH",
    "OPERATOR_ACTION_BY_IVA_LEDGER_AGGREGATION_ISSUE",
    "PARTY_ATTRIBUTED_ADDRESS_FIELDS",
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
    "ConfirmationRecordDocument",
    "ConfirmationRecordRepository",
    "ConfirmedCounterpartyFacts",
    "ConfirmedCounterpartyFactsInputError",
    "ConfirmedCounterpartyFactsRepository",
    "ConfirmedCounterpartyResolution",
    "ConfirmedEstablishment",
    "ConsentRederivationError",
    "ConsentWithdrawalSurvey",
    "ConsentedDispatch",
    "CounterpartyDraftSide",
    "CounterpartyEstablishment",
    "CounterpartyEstablishmentConflictError",
    "CounterpartyEstablishmentContradiction",
    "CountryVocabularyAdvisory",
    "CountryVocabularyWarning",
    "DeclaredFact",
    "DeclaredFacts",
    "DeterministicCheck",
    "DirectionDerivationOutcome",
    "DocumentTranscription",
    "DraftDiscrepancyFinding",
    "EligibleCategoryRow",
    "EstablishmentRung",
    "EvidenceInput",
    "ExportSerializationFormat",
    "ExtractedDocumentCacheRepository",
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
    "InvoiceExtractionAuthorityValues",
    "InvoiceKindDerivation",
    "IvaCategoryResolution",
    "LedgerCatalogueResetReport",
    "LedgerClassificationRuleRepository",
    "LedgerExportCommand",
    "LedgerExportResult",
    "LedgerExportRow",
    "LedgerImportDiagnosticReport",
    "LedgerImportOperationResult",
    "LedgerPreconditionCondition",
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
    "LlmUsageCostProviderMetrics",
    "LocalRederivation",
    "ManualLedgerTransactionCommand",
    "ManualLedgerTransactionPatch",
    "ManualLedgerTransactionResult",
    "MediaKind",
    "MergeTransactionsResult",
    "MissingClassifierInput",
    "OnHostReader",
    "PartyAddress",
    "PartyAttributionAdvisory",
    "PartyAttributionOutcome",
    "PartyAttributionWarning",
    "PartyColocationResolution",
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
    "RegistrationEstablishmentConflict",
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
    "assemble_classification_criteria",
    "attach_manual_transaction_evidence",
    "batch_item_identity",
    "build_confirmation_record",
    "build_llm_diagnostics_report",
    "bulk_classify_from_csv",
    "canonical_identity_token",
    "censo_business_pct_for",
    "censo_override_warning",
    "classify_from_assembled_criteria",
    "closure_findings",
    "collect_classifier_inputs",
    "compute_display_id_width",
    "confirm_invoice_draft_from_evidence",
    "confirmation_blockers",
    "confirmed_counterparty_facts_key",
    "counterparty_draft_side",
    "country_vocabulary_advisory",
    "create_manual_transaction",
    "declared_category_from_document_record",
    "default_invoice_extraction_period",
    "derive_confirmation_id",
    "derive_invoice_kind_from_filer_role",
    "derive_operator_iva_substrate",
    "describe_aeat_party_identifier",
    "detach_manual_transaction_attachments",
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
    "forget_confirmed_counterparty_facts",
    "get_manual_transaction",
    "get_transaction_participation",
    "ground_ambiguous_candidates",
    "ground_anchored_value",
    "ground_draft_against_transcription",
    "ground_self_reported_anchor",
    "import_ledger_source",
    "import_ledger_transactions",
    "ledger_no_recovery_verdict",
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
    "party_addresses",
    "party_attribution_advisory",
    "party_attribution_findings",
    "party_regions",
    "preflight_ledger_tax_readiness",
    "preflight_transaction_catalogue",
    "printed_excerpt_occurs",
    "printed_excerpt_occurs_in_text",
    "printed_total_discrepancy",
    "project_aeat_record_counterparty",
    "query_ledger_review_rows",
    "re_stamped_provenance",
    "read_confirmation_record",
    "read_extraction_draft",
    "record_confirmed_counterparty_facts",
    "rederive_artefact_on_host",
    "regime_contradiction_finding",
    "reject_llm_suggestion",
    "remove_manual_transaction",
    "reset_ledger_catalogue",
    "resolve_confirmed_counterparty_facts",
    "resolve_confirmed_establishment",
    "resolve_counterparty_establishment_scope",
    "resolve_counterparty_identity",
    "resolve_draft_counterparty_establishment",
    "resolve_filer_tax_id",
    "resolve_filer_territorial_scope",
    "resolve_ingestion_iva_category",
    "resolve_invoice_extraction_authority_values",
    "resolve_lineage_transaction_id",
    "resolve_party_attribution_by_colocation",
    "resolve_transaction_id",
    "resolved_blockers",
    "restore_manual_transaction",
    "review_advisory_kinds",
    "run_evidence_batch",
    "saturate_llm_classification",
    "scope_printed_evidence_would_establish",
    "set_usage_ratio",
    "split_transaction",
    "split_transaction_with_classified_children",
    "stamp_unverified_party_attribution",
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
    "write_cached_transcription",
    "write_confirmation_record",
    "write_extraction_draft",
]
